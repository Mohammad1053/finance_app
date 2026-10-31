import datetime as dt

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.models import Goal, GoalContribution

router = APIRouter(include_in_schema=False)
templates = Jinja2Templates(directory="app/templates")


def _render(request: Request, db: Session, error: str = ""):
    """Render the goals list partial with an optional error message."""
    goals = (
        db.query(Goal)
        .options(selectinload(Goal.contributions))
        .order_by(Goal.name)
        .all()
    )
    return templates.TemplateResponse(
        request, "partials/goals_list.html", {"goals": goals, "error": error}
    )


@router.get("/goals", response_class=HTMLResponse)
def goals_page(request: Request):
    """Goals page; the list itself is loaded by HTMX."""
    return templates.TemplateResponse(request, "goals.html", {})


@router.get("/ui/goals", response_class=HTMLResponse)
def goals_list(request: Request, db: Session = Depends(get_db)):
    """Return the goals list partial."""
    return _render(request, db)


@router.post("/ui/goals", response_class=HTMLResponse)
def add_goal(
    request: Request,
    name: str = Form(...),
    target_amount: int = Form(gt=0),
    db: Session = Depends(get_db),
):
    """Create a goal; report an error if the name already exists."""
    db.add(Goal(name=name.strip(), target_amount=target_amount))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return _render(request, db, "هدفی با این نام قبلاً ثبت شده است.")
    return _render(request, db)


@router.post("/ui/goals/{goal_id}/contributions", response_class=HTMLResponse)
def add_contribution(
    goal_id: int,
    request: Request,
    amount: int = Form(gt=0),
    db: Session = Depends(get_db),
):
    """Add a deposit to a goal, dated today."""
    goal = db.get(Goal, goal_id)
    if goal:
        db.add(GoalContribution(goal_id=goal.id,
               amount=amount, date=dt.date.today()))
        db.commit()
    return _render(request, db)


@router.delete("/ui/goals/{goal_id}", response_class=HTMLResponse)
def delete_goal(goal_id: int, request: Request, db: Session = Depends(get_db)):
    """Delete a goal together with its contributions."""
    goal = db.get(Goal, goal_id)
    if goal:
        db.delete(goal)
        db.commit()
    return _render(request, db)
