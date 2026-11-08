from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.schema import CreateColumn

from app.database import Base


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

    Returns the list of added columns as 'table.column'. Existing data is never changed.
    """
    from app import models  # noqa: F401  (registers every table on Base.metadata)
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    added: list[str] = []

    with engine.begin() as conn:
        for table in Base.metadata.sorted_tables:
            if table.name not in existing_tables:
                continue  # new tables are created by create_all
            present = {c["name"] for c in inspector.get_columns(table.name)}
            for column in table.columns:
                if column.name in present:
                    continue
                if column.primary_key:
                    raise RuntimeError(f"Cannot add primary key column {table.name}.{column.name}")

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
                    ddl = parts[0] + default_sql + (" NOT NULL" if len(parts) > 1 else "")
                conn.execute(text(f'ALTER TABLE "{table.name}" ADD COLUMN {ddl}'))
                added.append(f"{table.name}.{column.name}")
    return added
