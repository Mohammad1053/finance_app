from sqlalchemy.orm import Session


def owned(db: Session, model, object_id: int, user_id: int):
    """Return the row with this id only if it belongs to the user, else None."""
    return db.query(model).filter(model.id == object_id, model.user_id == user_id).first()
