import logging
import os
import secrets
import shutil

from sqlalchemy import inspect, insert, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.schema import CreateColumn

from app.database import Base

logger = logging.getLogger("uvicorn.error")

# Tables that hold user data, parents first. Rows are re-inserted in this exact
# order, so every child row finds its parent row before it is written.
DATA_TABLES = [
    "payment_methods",
    "categories",
    "goals",
    "transactions",
    "goal_contributions",
    "recurring_transactions",
]
# Children first, plus the two single-user tables that no longer exist.
DROP_ORDER = [
    "goal_contributions",
    "recurring_transactions",
    "transactions",
    "goals",
    "categories",
    "payment_methods",
    "app_settings",
    "auth_settings",
]


def _default_sql(column) -> str:
    """Return a SQL DEFAULT clause for a column, or an empty string."""
    default = column.default
    if default is None or not getattr(default, "is_scalar", False):
        return ""
    value = default.arg
    if isinstance(value, bool):
        return f" DEFAULT {int(value)}"
    if isinstance(value, (int, float)):
        return f" DEFAULT {value}"
    if isinstance(value, str):
        escaped = value.replace("'", "''")
        return f" DEFAULT '{escaped}'"
    return ""


def add_missing_columns(engine: Engine) -> list[str]:
    """Add columns that exist in the models but not in the database.

    Returns the list of added columns as 'table.column'. Existing data is never
    changed. The inspector is rebuilt for every table so an earlier ALTER TABLE
    cannot leave a stale column cache behind.
    """
    from app import models  # noqa: F401  (registers every table on Base.metadata)

    existing_tables = set(inspect(engine).get_table_names())
    added: list[str] = []

    with engine.begin() as conn:
        for table in Base.metadata.sorted_tables:
            if table.name not in existing_tables:
                continue  # new tables are created by create_all

            # Rebuild the inspector for this table: an earlier ALTER TABLE on
            # another table can invalidate the cached column list.
            present = {c["name"]
                       for c in inspect(engine).get_columns(table.name)}

            for column in table.columns:
                if column.name in present:
                    continue
                if column.primary_key:
                    raise RuntimeError(
                        f"Cannot add primary key column {table.name}.{column.name}"
                    )

                default_sql = _default_sql(column)
                if not column.nullable and not default_sql:
                    raise RuntimeError(
                        f"Column {table.name}.{column.name} is NOT NULL without a default; "
                        "give it a default or migrate it manually"
                    )

                ddl = str(CreateColumn(column).compile(dialect=engine.dialect))
                # CreateColumn does not include Python-side defaults, so add the SQL one
                if default_sql and "DEFAULT" not in ddl:
                    parts = ddl.split(" NOT NULL")
                    ddl = parts[0] + default_sql + \
                        (" NOT NULL" if len(parts) > 1 else "")
                conn.execute(
                    text(f'ALTER TABLE "{table.name}" ADD COLUMN {ddl}'))
                added.append(f"{table.name}.{column.name}")
    return added


def _backup_sqlite_file(engine: Engine) -> None:
    """Copy the SQLite file next to itself before the one-time multi-user migration."""
    path = engine.url.database
    if engine.url.get_backend_name() != "sqlite" or not path or path == ":memory:":
        return
    backup = f"{path}.pre-multiuser.bak"
    if os.path.exists(path) and not os.path.exists(backup):
        shutil.copy2(path, backup)


def _first_row(conn, table: str, names: set[str]) -> dict:
    """Return the first row of a table as a dict, or {} when the table is missing or empty."""
    if table not in names:
        return {}
    row = conn.execute(text(f'SELECT * FROM "{table}"')).mappings().first()
    return dict(row) if row else {}


def migrate_legacy_single_user(engine: Engine) -> bool:
    """Convert a single-user database into a multi-user one. Returns True when it ran.

    All old data moves to one account (LEGACY_OWNER_USERNAME, default "owner").
    Its password is LEGACY_OWNER_PASSWORD, else the old app password, else a
    random one that is written to the log once. A backup file is created first.
    """
    from app import models  # noqa: F401  (registers every table on Base.metadata)
    from app.services import auth

    inspector = inspect(engine)
    names = set(inspector.get_table_names())
    if "categories" not in names:
        return False  # brand new database
    if "user_id" in {c["name"] for c in inspector.get_columns("categories")}:
        return False  # already migrated

    _backup_sqlite_file(engine)

    # 1. Read everything into memory before touching the schema
    with engine.connect() as conn:
        rows: dict[str, list[dict]] = {}
        for name in DATA_TABLES:
            if name not in names:
                rows[name] = []
                continue
            table = Base.metadata.tables[name]
            present = {c["name"] for c in inspector.get_columns(name)}
            columns = [c for c in table.c if c.name in present]
            rows[name] = [dict(r._mapping)
                          for r in conn.execute(select(*columns))]
        profile = _first_row(conn, "app_settings", names)
        legacy_auth = _first_row(conn, "auth_settings", names)

    # 2. Drop the old tables and build the new schema in one transaction so a
    # failure cannot leave the database without any tables.
    with engine.begin() as conn:
        for name in DROP_ORDER:
            conn.execute(text(f'DROP TABLE IF EXISTS "{name}"'))
        Base.metadata.create_all(bind=conn)

    has_data = any(rows[n]
                   for n in DATA_TABLES) or bool(profile.get("first_name"))
    if not has_data:
        return True

    # 3. Create the owner account and re-insert every row with its owner.
    # DATA_TABLES is ordered parents-first, so a child row never precedes its parent.
    username = auth.normalize_username(
        os.getenv("LEGACY_OWNER_USERNAME", "owner")) or "owner"
    password = os.getenv("LEGACY_OWNER_PASSWORD", "")
    generated = False
    if password:
        password_hash = auth.hash_password(password)
    elif legacy_auth.get("password_hash"):
        # the old app password keeps working
        password_hash = legacy_auth["password_hash"]
    else:
        password = secrets.token_urlsafe(9)
        password_hash = auth.hash_password(password)
        generated = True

    with engine.begin() as conn:
        # Build the Insert from the mapped class (not from __table__): only then
        # does SQLAlchemy know which column is the primary key.
        result = conn.execute(
            insert(models.User).values(
                username=username,
                first_name=profile.get("first_name") or "",
                last_name=profile.get("last_name") or "",
                password_hash=password_hash,
                session_secret=auth.new_secret(),
                theme=profile.get("theme") or "light",
                currency=profile.get("currency") or "toman",
                defaults_seeded=True,
            )
        )
        # inserted_primary_key is not populated on every dialect for a raw
        # connection.execute(insert(...)). Try the portable sources in order.
        owner_id = result.inserted_primary_key[0] if result.inserted_primary_key else None
        if owner_id is None:
            owner_id = result.lastrowid  # SQLite and MySQL
        if owner_id is None:
            owner_id = conn.execute(
                select(models.User.id).where(models.User.username == username)
            ).scalar_one()

        for name in DATA_TABLES:
            if not rows[name]:
                continue
            table = Base.metadata.tables[name]
            if "user_id" in table.c:
                payload = [{**row, "user_id": owner_id} for row in rows[name]]
            else:
                payload = rows[name]
            conn.execute(table.insert(), payload)

    logger.warning(
        "Single-user data moved to account '%s' (backup: *.pre-multiuser.bak)", username
    )
    if generated:
        logger.warning(
            "Temporary password for '%s': %s  (change it in the appearance settings)",
            username,
            password,
        )
    return True
