import datetime as dt

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.deps import currency_of, require_user
from app.models import Goal, GoalContribution, User
from app.ownership import owned
from app.templating import templates
from app.units import to_base

router = APIRouter(include_in_schema=False)


def _render(request: Request, db: Session, user: User, error: str = ""):
    """Render the goals list partial with an optional error message."""
    goals = (
        db.query(Goal)
        .options(selectinload(Goal.contributions))
        .filter(Goal.user_id == user.id)
        .order_by(Goal.name)
        .all()
    )
    return templates.TemplateResponse(
        request, "partials/goals_list.html", {"goals": goals, "error": error}
    )


@router.get("/goals", response_class=HTMLResponse, dependencies=[Depends(require_user)])
def goals_page(request: Request):
    """Goals page; the list itself is loaded by HTMX."""
    return templates.TemplateResponse(request, "goals.html", {})


@router.get("/ui/goals", response_class=HTMLResponse)
def goals_list(request: Request, db: Session = Depends(get_db), user: User = Depends(require_user)):
    """Return the goals list partial."""
    return _render(request, db, user)


@router.post("/ui/goals", response_class=HTMLResponse)
def add_goal(
    request: Request,
    name: str = Form(...),
    target_amount: int = Form(gt=0),
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    """Create a goal; report an error if the user already has that name."""
    db.add(
        Goal(
            user_id=user.id,
            name=name.strip(),
            target_amount=to_base(target_amount, currency_of(request)),
        )
    )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return _render(request, db, user, "هدفی با این نام قبلاً ثبت شده است.")
    return _render(request, db, user)


@router.post("/ui/goals/{goal_id}/contributions", response_class=HTMLResponse)
def add_contribution(
    goal_id: int,
    request: Request,
    amount: int = Form(gt=0),
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    """Add a deposit to one of the user's goals, dated today."""
    goal = owned(db, Goal, goal_id, user.id)
    if goal:
        db.add(
            GoalContribution(
                goal_id=goal.id, amount=to_base(amount, currency_of(request)), date=dt.date.today()
            )
        )
        db.commit()
    return _render(request, db, user)


@router.delete("/ui/goals/{goal_id}", response_class=HTMLResponse)
def delete_goal(
    goal_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    """Delete one of the user's goals together with its contributions."""
    goal = owned(db, Goal, goal_id, user.id)
    if goal:
        db.delete(goal)
        db.commit()
    return _render(request, db, user)
