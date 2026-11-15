"""Agrégats pour le suivi de progression."""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from datetime import date, timedelta

from .models import LoggedSession, PlannedSession, Sport

# Le « brick » (course après vélo) compte comme de la course à pied
CHART_SPORTS = ("swim", "bike", "run")


def monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


def _bucket(sport: Sport | str) -> str | None:
    s = Sport(sport).value
    if s == "brick":
        return "run"
    if s == "race":
        return None  # la course elle-même n'est pas du volume d'entraînement
    return s if s in CHART_SPORTS else None


def weekly_volume(
    logs: Iterable[LoggedSession],
    planned: Iterable[PlannedSession],
) -> list[dict]:
    """Minutes réalisées par sport et minutes prévues, par semaine (lundi)."""
    done: dict[date, dict[str, int]] = defaultdict(lambda: dict.fromkeys(CHART_SPORTS, 0))
    plan: dict[date, int] = defaultdict(int)
    for log in logs:
        b = _bucket(log.sport)
        if b:
            done[monday(log.date)][b] += log.duration_min
    for p in planned:
        if _bucket(p.sport):
            plan[monday(p.date)] += p.duration_min

    weeks = sorted(set(done) | set(plan))
    if not weeks:
        return []
    # semaines continues, sans trou
    out = []
    w = weeks[0]
    while w <= weeks[-1]:
        row = {"week": w.isoformat(), "planned": plan.get(w, 0)}
        row.update(done.get(w, dict.fromkeys(CHART_SPORTS, 0)))
        out.append(row)
        w += timedelta(days=7)
    return out


def totals(logs: Iterable[LoggedSession]) -> dict[str, dict[str, float]]:
    out = {s: {"sessions": 0, "minutes": 0, "km": 0.0} for s in CHART_SPORTS}
    for log in logs:
        b = _bucket(log.sport)
        if not b:
            continue
        out[b]["sessions"] += 1
        out[b]["minutes"] += log.duration_min
        out[b]["km"] += log.distance_km or 0.0
    for s in out.values():
        s["km"] = round(s["km"], 1)
    return out


def compliance(planned: Iterable[PlannedSession], logs: Iterable[LoggedSession], until: date) -> int | None:
    """% de séances prévues (hors repos) jusqu'à `until` qui ont été validées."""
    due = [p for p in planned if p.date <= until and p.sport != Sport.REST]
    if not due:
        return None
    validated = {log.planned_id for log in logs if log.planned_id}
    return round(100 * sum(1 for p in due if p.id in validated) / len(due))


def pace_label(sport: Sport | str, minutes: int, km: float | None) -> str:
    """Allure lisible : min/100 m natation, km/h vélo, min/km course."""
    if not km or km <= 0 or minutes <= 0:
        return ""
    s = Sport(sport).value
    if s == "swim":
        sec = minutes * 60 / (km * 10)
        return f"{int(sec // 60)}'{int(sec % 60):02d}/100 m"
    if s == "bike":
        return f"{km / (minutes / 60):.1f} km/h"
    if s in ("run", "brick"):
        sec = minutes * 60 / km
        return f"{int(sec // 60)}'{int(sec % 60):02d}/km"
    return ""
