"""Application FastAPI : pages HTML (Jinja + HTMX) et petite API JSON."""

from contextlib import asynccontextmanager
from datetime import date, timedelta
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, Form, HTTPException, Request, Response
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, delete, select

from . import stats
from .db import init_db, make_engine, session_factory
from .models import (
    LOGGABLE_SPORTS,
    PHASE_LABELS,
    SPORT_ICONS,
    SPORT_LABELS,
    LoggedSession,
    PlannedSession,
    Settings,
    Sport,
)
from .plan import generate_plan

BASE_DIR = Path(__file__).parent
STATIC_DIR = BASE_DIR / "static"

DAYS = ["lun.", "mar.", "mer.", "jeu.", "ven.", "sam.", "dim."]
MONTHS = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."]


def fr_date(d: date, with_day: bool = True) -> str:
    s = f"{d.day} {MONTHS[d.month - 1]}"
    return f"{DAYS[d.weekday()]} {s}" if with_day else s


def fmt_duration(minutes: int | None) -> str:
    if not minutes:
        return "—"
    h, m = divmod(int(minutes), 60)
    if h and m:
        return f"{h}h{m:02d}"
    return f"{h}h" if h else f"{m} min"


def get_settings(session: Session) -> Settings:
    settings = session.get(Settings, 1)
    if settings is None:
        settings = Settings(id=1)
        session.add(settings)
        session.commit()
        session.refresh(settings)
    return settings


def regenerate_plan(session: Session, settings: Settings, today: date | None = None) -> None:
    """(Re)génère le plan et rattache les séances déjà validées (même date + sport)."""
    assert settings.race_date is not None
    plan = generate_plan(settings.race_date, settings.peak_hours, today=today)

    old = {p.id: (p.date, p.sport) for p in session.exec(select(PlannedSession)).all()}
    linked = session.exec(select(LoggedSession).where(LoggedSession.planned_id.is_not(None))).all()
    keys = {log.id: old.get(log.planned_id, (log.date, log.sport)) for log in linked}
    for log in linked:
        log.planned_id = None
        session.add(log)
    session.flush()
    session.exec(delete(PlannedSession))
    session.add_all(plan.sessions)
    session.flush()

    by_key = {(p.date, p.sport): p.id for p in plan.sessions}
    for log in linked:
        log.planned_id = by_key.get(keys[log.id])
        session.add(log)
    session.commit()


def create_app(db_url: str | None = None) -> FastAPI:
    engine = make_engine(db_url)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        init_db(engine)
        yield

    app = FastAPI(title="Triathlon Trainer", lifespan=lifespan)
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    templates = Jinja2Templates(directory=BASE_DIR / "templates")
    templates.env.filters["frdate"] = fr_date
    templates.env.filters["duration"] = fmt_duration
    templates.env.globals.update(
        SPORT_LABELS=SPORT_LABELS,
        SPORT_ICONS=SPORT_ICONS,
        PHASE_LABELS=PHASE_LABELS,
        LOGGABLE_SPORTS=LOGGABLE_SPORTS,
        pace=stats.pace_label,
    )

    get_session = session_factory(engine)
    DB = Annotated[Session, Depends(get_session)]

    def render(request: Request, name: str, **ctx) -> HTMLResponse:
        return templates.TemplateResponse(request, name, ctx)

    def today() -> date:
        return date.today()

    # --- PWA ------------------------------------------------------------
    @app.get("/sw.js", include_in_schema=False)
    def service_worker():
        return FileResponse(
            STATIC_DIR / "sw.js",
            media_type="application/javascript",
            headers={"Cache-Control": "no-cache"},
        )

    @app.get("/manifest.webmanifest", include_in_schema=False)
    def manifest():
        return FileResponse(STATIC_DIR / "manifest.webmanifest", media_type="application/manifest+json")

    @app.get("/healthz", include_in_schema=False)
    def healthz():
        return {"status": "ok"}

    # --- Tableau de bord ------------------------------------------------
    @app.get("/", response_class=HTMLResponse)
    def dashboard(request: Request, db: DB):
        settings = get_settings(db)
        t = today()
        planned = db.exec(select(PlannedSession).order_by(PlannedSession.date)).all()
        logs = db.exec(select(LoggedSession)).all()
        done_ids = {log.planned_id for log in logs if log.planned_id}

        current_week = None
        week_sessions: list[PlannedSession] = []
        if planned:
            start = planned[0].date
            idx = max(0, (t - start).days // 7) + 1
            idx = min(idx, planned[-1].week)
            current_week = idx
            week_sessions = [p for p in planned if p.week == idx]

        week_planned = sum(p.duration_min for p in week_sessions if p.sport not in (Sport.REST, Sport.RACE))
        week_ids = {p.id for p in week_sessions}
        week_done = sum(log.duration_min for log in logs if log.planned_id in week_ids)

        return render(
            request,
            "dashboard.html",
            settings=settings,
            today=t,
            days_left=(settings.race_date - t).days if settings.race_date else None,
            current_week=current_week,
            n_weeks=planned[-1].week if planned else 0,
            plan_start=planned[0].date if planned else None,
            week_sessions=week_sessions,
            done_ids=done_ids,
            week_planned=week_planned,
            week_done=week_done,
            compliance=stats.compliance(planned, logs, t),
        )

    # --- Plan -----------------------------------------------------------
    @app.get("/plan", response_class=HTMLResponse)
    def plan_page(request: Request, db: DB):
        planned = db.exec(select(PlannedSession).order_by(PlannedSession.date, PlannedSession.id)).all()
        logs = db.exec(select(LoggedSession)).all()
        weeks: dict[int, list[PlannedSession]] = {}
        for p in planned:
            weeks.setdefault(p.week, []).append(p)
        t = today()
        return render(
            request,
            "plan.html",
            settings=get_settings(db),
            weeks=weeks,
            done_ids={log.planned_id for log in logs if log.planned_id},
            today=t,
            current_monday=t - timedelta(days=t.weekday()),
        )

    # --- Journal --------------------------------------------------------
    @app.get("/journal", response_class=HTMLResponse)
    def journal(request: Request, db: DB):
        logs = db.exec(select(LoggedSession).order_by(LoggedSession.date.desc(), LoggedSession.id.desc())).all()
        return render(request, "journal.html", logs=logs, settings=get_settings(db))

    @app.get("/journal/form", response_class=HTMLResponse)
    def journal_form(request: Request, db: DB, planned_id: int | None = None):
        planned = db.get(PlannedSession, planned_id) if planned_id else None
        return render(request, "partials/log_form.html", planned=planned, today=today())

    @app.post("/journal")
    def create_log(
        request: Request,
        db: DB,
        date_: Annotated[date, Form(alias="date")],
        sport: Annotated[Sport, Form()],
        duration_min: Annotated[int, Form(gt=0, le=1440)],
        distance_km: Annotated[str, Form()] = "",
        rpe: Annotated[str, Form()] = "",
        avg_hr: Annotated[str, Form()] = "",
        notes: Annotated[str, Form()] = "",
        planned_id: Annotated[str, Form()] = "",
    ):
        if sport == Sport.REST:
            raise HTTPException(422, "Une séance de repos ne se saisit pas.")
        log = LoggedSession(
            date=date_,
            sport=sport,
            duration_min=duration_min,
            distance_km=float(distance_km.replace(",", ".")) if distance_km.strip() else None,
            rpe=int(rpe) if rpe.strip() else None,
            avg_hr=int(avg_hr) if avg_hr.strip() else None,
            notes=notes.strip(),
            planned_id=int(planned_id) if planned_id.strip() else None,
        )
        if log.planned_id and db.get(PlannedSession, log.planned_id) is None:
            log.planned_id = None
        db.add(log)
        db.commit()
        if request.headers.get("HX-Request"):
            return Response(status_code=204, headers={"HX-Refresh": "true"})
        return RedirectResponse("/journal", status_code=303)

    @app.delete("/journal/{log_id}")
    def delete_log(log_id: int, db: DB):
        log = db.get(LoggedSession, log_id)
        if log is None:
            raise HTTPException(404)
        db.delete(log)
        db.commit()
        return HTMLResponse("")

    # --- Progression ----------------------------------------------------
    @app.get("/progress", response_class=HTMLResponse)
    def progress(request: Request, db: DB):
        logs = db.exec(select(LoggedSession)).all()
        planned = db.exec(select(PlannedSession)).all()
        return render(
            request,
            "progress.html",
            totals=stats.totals(logs),
            compliance=stats.compliance(planned, logs, today()),
            has_data=bool(logs or planned),
        )

    @app.get("/api/stats/weekly")
    def api_weekly(db: DB):
        logs = db.exec(select(LoggedSession)).all()
        planned = db.exec(select(PlannedSession)).all()
        return stats.weekly_volume(logs, planned)

    # --- Réglages -------------------------------------------------------
    @app.get("/settings", response_class=HTMLResponse)
    def settings_page(request: Request, db: DB):
        return render(request, "settings.html", settings=get_settings(db), error=None, today=today())

    @app.post("/settings", response_class=HTMLResponse)
    def save_settings(
        request: Request,
        db: DB,
        race_name: Annotated[str, Form()],
        race_date: Annotated[date, Form()],
        peak_hours: Annotated[float, Form(gt=2, le=25)],
    ):
        settings = get_settings(db)
        settings.race_name = race_name.strip() or "Triathlon M"
        settings.race_date = race_date
        settings.peak_hours = peak_hours
        try:
            regenerate_plan(db, settings, today=today())
        except ValueError as exc:
            db.rollback()
            return render(request, "settings.html", settings=settings, error=str(exc), today=today())
        db.add(settings)
        db.commit()
        return RedirectResponse("/plan", status_code=303)

    return app


app = create_app()
