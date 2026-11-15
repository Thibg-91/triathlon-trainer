"""Modèles de données (SQLModel = SQLAlchemy + Pydantic)."""
from __future__ import annotations

import datetime as dt
from enum import Enum

from sqlmodel import Field, SQLModel


class Sport(str, Enum):
    SWIM = "swim"
    BIKE = "bike"
    RUN = "run"
    BRICK = "brick"  # enchaînement vélo -> course
    STRENGTH = "strength"
    RACE = "race"
    REST = "rest"


SPORT_LABELS: dict[str, str] = {
    "swim": "Natation",
    "bike": "Vélo",
    "run": "Course à pied",
    "brick": "Enchaînement",
    "strength": "Renfo",
    "race": "Course !",
    "rest": "Repos",
}

SPORT_ICONS: dict[str, str] = {
    "swim": "🏊",
    "bike": "🚴",
    "run": "🏃",
    "brick": "🔁",
    "strength": "💪",
    "race": "🏁",
    "rest": "😴",
}

# Sports qu'on peut saisir dans le journal
LOGGABLE_SPORTS = [Sport.SWIM, Sport.BIKE, Sport.RUN, Sport.BRICK, Sport.STRENGTH, Sport.RACE]


class Phase(str, Enum):
    BASE = "base"
    BUILD = "build"
    PEAK = "peak"
    TAPER = "taper"


PHASE_LABELS: dict[str, str] = {
    "base": "Foncier",
    "build": "Développement",
    "peak": "Spécifique",
    "taper": "Affûtage",
}


class Settings(SQLModel, table=True):
    """Paramètres de l'athlète et de l'objectif (une seule ligne, id=1)."""

    id: int | None = Field(default=1, primary_key=True)
    race_name: str = "Triathlon M"
    race_date: dt.date | None = None
    peak_hours: float = 8.0  # volume hebdo visé au pic (heures)


class PlannedSession(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    date: dt.date = Field(index=True)
    week: int  # 1..N
    phase: Phase
    recovery_week: bool = False
    sport: Sport
    title: str
    description: str = ""
    duration_min: int = 0
    intensity: str = ""  # ex. "Z2", "Z4", "Allure course"


class LoggedSession(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    date: dt.date = Field(index=True)
    sport: Sport
    duration_min: int
    distance_km: float | None = None
    rpe: int | None = Field(default=None, ge=1, le=10)  # ressenti 1..10
    avg_hr: int | None = None
    notes: str = ""
    planned_id: int | None = Field(default=None, foreign_key="plannedsession.id")
