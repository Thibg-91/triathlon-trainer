"""Générateur de plan d'entraînement pour triathlon distance M.

Distance M (olympique) : 1,5 km natation / 40 km vélo / 10 km course.

Le plan est une fonction pure (aucun accès base) : facile à tester et à faire
évoluer. Principes retenus :

* périodisation Foncier -> Développement -> Spécifique -> Affûtage ;
* cycles 3:1 (une semaine allégée toutes les 4 semaines en foncier/dév.) ;
* 6 séances par semaine : 2 natation, 2 vélo, 2 course, 1 jour de repos ;
* enchaînement vélo -> course (« brick ») à partir de la phase de développement ;
* la dernière semaine se termine le jour de la course.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

from .models import Phase, PlannedSession, Sport

MIN_WEEKS = 3
MAX_WEEKS = 16


@dataclass(frozen=True)
class WeekSpec:
    week: int  # 1..N
    start: date
    phase: Phase
    load: float  # fraction du volume pic (0..1)
    recovery: bool = False


@dataclass(frozen=True)
class SessionSpec:
    offset: int  # jour dans la semaine 0..6 (6 = dernier jour)
    sport: Sport
    title: str
    description: str
    duration_min: int
    intensity: str = ""


@dataclass
class Plan:
    race_date: date
    weeks: list[WeekSpec]
    sessions: list[PlannedSession] = field(default_factory=list)

    @property
    def start_date(self) -> date:
        return self.weeks[0].start


def _round5(minutes: float, minimum: int = 20) -> int:
    return max(minimum, int(5 * round(minutes / 5)))


def phase_split(n_weeks: int) -> dict[Phase, int]:
    """Répartition du nombre de semaines par phase."""
    taper = 2 if n_weeks >= 8 else 1
    if n_weeks >= 14:
        peak = 3
    elif n_weeks >= 8:
        peak = 2
    elif n_weeks >= 5:
        peak = 1
    else:
        peak = 0
    remaining = n_weeks - taper - peak
    build = remaining // 2
    base = remaining - build
    return {Phase.BASE: base, Phase.BUILD: build, Phase.PEAK: peak, Phase.TAPER: taper}


def build_weeks(race_date: date, today: date) -> list[WeekSpec]:
    days_available = (race_date - today).days + 1
    weeks_available = days_available // 7
    if weeks_available < MIN_WEEKS:
        raise ValueError(
            f"Il faut au moins {MIN_WEEKS} semaines avant la course pour générer un plan "
            f"(il en reste {max(weeks_available, 0)})."
        )
    n = min(weeks_available, MAX_WEEKS)
    start = race_date - timedelta(days=7 * n - 1)
    split = phase_split(n)

    weeks: list[WeekSpec] = []
    w = 0
    progressive_idx = 0  # compteur foncier + développement pour les cycles 3:1

    def add(phase: Phase, load: float, recovery: bool = False) -> None:
        nonlocal w
        weeks.append(WeekSpec(w + 1, start + timedelta(days=7 * w), phase, round(load, 3), recovery))
        w += 1

    for phase, lo, hi in ((Phase.BASE, 0.55, 0.75), (Phase.BUILD, 0.75, 0.9)):
        count = split[phase]
        for i in range(count):
            load = lo + (hi - lo) * (i / max(count - 1, 1))
            progressive_idx += 1
            recovery = progressive_idx % 4 == 0
            add(phase, load * 0.65 if recovery else load, recovery)
    for _ in range(split[Phase.PEAK]):
        add(Phase.PEAK, 1.0)
    taper_loads = [0.7, 0.45] if split[Phase.TAPER] == 2 else [0.45]
    for load in taper_loads:
        add(Phase.TAPER, load)
    return weeks


# --- Contenu des séances --------------------------------------------------

def _swim_quality(phase: Phase, recovery: bool) -> tuple[str, str, str]:
    if recovery:
        return "Natation technique", "Éducatifs (rattrapé, poings fermés, 6 battements/1 bras) + nage souple.", "Z1-Z2"
    return {
        Phase.BASE: ("Natation technique", "Échauffement 300 m, 8×50 m éducatifs, 6×100 m souple r=20 s, retour au calme.", "Z2"),
        Phase.BUILD: ("Natation fractionné", "Échauffement 400 m, 10×100 m allure seuil r=15 s, 200 m pull-buoy, retour au calme.", "Z4"),
        Phase.PEAK: ("Natation allure course", "Échauffement 400 m, 3×500 m allure 1,5 km r=30 s, 4×50 m sprint départ.", "Allure course"),
        Phase.TAPER: ("Natation activation", "Échauffement 300 m, 6×100 m allure course r=30 s, 4×25 m vite.", "Allure course"),
    }[phase]


def _swim_endurance(phase: Phase, recovery: bool) -> tuple[str, str, str]:
    if phase in (Phase.PEAK, Phase.BUILD) and not recovery:
        return "Natation endurance", "Nage continue 1 500 m+ en eau libre ou bassin, travail de visée tous les 6 mouvements.", "Z2-Z3"
    return "Natation endurance", "Nage continue en aisance respiratoire, respiration tous les 3 temps.", "Z2"


def _run_quality(phase: Phase, recovery: bool) -> tuple[str, str, str]:
    if recovery:
        return "Footing", "Footing souple + 6 lignes droites de 20 s.", "Z2"
    return {
        Phase.BASE: ("Course fartlek", "20 min footing, 8×1 min rapide / 1 min lent, retour au calme.", "Z2-Z4"),
        Phase.BUILD: ("Course seuil", "20 min footing, 3×8 min allure seuil r=2 min, retour au calme.", "Z4"),
        Phase.PEAK: ("Course allure 10 km", "20 min footing, 2×15 min allure 10 km tri r=3 min, retour au calme.", "Allure course"),
        Phase.TAPER: ("Course activation", "Footing + 4×1 min allure course r=1 min.", "Allure course"),
    }[phase]


def _run_long(phase: Phase, recovery: bool) -> tuple[str, str, str]:
    if phase is Phase.PEAK and not recovery:
        return "Sortie longue course", "Sortie longue avec les 15 dernières minutes à allure course.", "Z2 + allure course"
    return "Sortie longue course", "Footing long en endurance fondamentale, sur terrain varié.", "Z2"


def _bike_quality(phase: Phase, recovery: bool) -> tuple[str, str, str]:
    if recovery:
        return "Vélo souple", "Vélo en endurance, cadence élevée (90-95 rpm).", "Z2"
    return {
        Phase.BASE: ("Vélo force/cadence", "Échauffement 15 min, 5×3 min gros braquet 60 rpm / 2 min vélocité, retour au calme.", "Z3"),
        Phase.BUILD: ("Vélo seuil", "Échauffement 15 min, 3×10 min allure seuil r=4 min, retour au calme.", "Z4"),
        Phase.PEAK: ("Vélo allure course", "Échauffement 15 min, 2×20 min allure 40 km r=5 min, retour au calme.", "Allure course"),
        Phase.TAPER: ("Vélo activation", "Échauffement, 3×3 min allure course r=3 min, retour au calme.", "Allure course"),
    }[phase]


def _bike_long(phase: Phase, recovery: bool) -> tuple[str, str, str]:
    if phase is Phase.PEAK and not recovery:
        return "Sortie longue vélo", "Sortie longue dont 2×15 min allure course. Tester la nutrition de course.", "Z2 + allure course"
    return "Sortie longue vélo", "Sortie longue en endurance, s'alimenter toutes les 30-40 min.", "Z2"


# Pondération du volume hebdomadaire par créneau
WEIGHTS = {
    "swim_q": 0.12,
    "run_q": 0.13,
    "bike_q": 0.17,
    "swim_e": 0.12,
    "bike_l": 0.28,
    "run_l": 0.18,
}
BRICK_SHARE = 0.06  # part retirée de la sortie longue vélo pour l'enchaînement


def week_sessions(week: WeekSpec, peak_hours: float, is_last: bool) -> list[SessionSpec]:
    if is_last:
        return race_week_sessions()

    minutes = peak_hours * 60 * week.load
    p, r = week.phase, week.recovery
    with_brick = p in (Phase.BUILD, Phase.PEAK) and not r
    bike_long_w = WEIGHTS["bike_l"] - (BRICK_SHARE if with_brick else 0)

    def mk(offset: int, sport: Sport, content: tuple[str, str, str], weight: float) -> SessionSpec:
        title, desc, intensity = content
        return SessionSpec(offset, sport, title, desc, _round5(minutes * weight), intensity)

    sessions = [
        SessionSpec(0, Sport.REST, "Repos", "Récupération : sommeil, hydratation, mobilité légère.", 0),
        mk(1, Sport.SWIM, _swim_quality(p, r), WEIGHTS["swim_q"]),
        mk(2, Sport.RUN, _run_quality(p, r), WEIGHTS["run_q"]),
        mk(3, Sport.BIKE, _bike_quality(p, r), WEIGHTS["bike_q"]),
        mk(4, Sport.SWIM, _swim_endurance(p, r), WEIGHTS["swim_e"]),
        mk(5, Sport.BIKE, _bike_long(p, r), bike_long_w),
    ]
    if with_brick:
        sessions.append(
            SessionSpec(
                5,
                Sport.BRICK,
                "Enchaînement course",
                "Course à pied juste après le vélo : transition rapide, premiers km à allure course.",
                _round5(minutes * BRICK_SHARE, minimum=10),
                "Allure course",
            )
        )
    sessions.append(mk(6, Sport.RUN, _run_long(p, r), WEIGHTS["run_l"]))
    return sessions


def race_week_sessions() -> list[SessionSpec]:
    return [
        SessionSpec(0, Sport.REST, "Repos", "Repos complet.", 0),
        SessionSpec(1, Sport.SWIM, "Natation rappel", "800-1 000 m dont 4×100 m allure course.", 30, "Allure course"),
        SessionSpec(2, Sport.RUN, "Footing + lignes droites", "Footing 25 min + 4 lignes droites.", 30, "Z2"),
        SessionSpec(3, Sport.BIKE, "Vélo déblocage", "45 min souple avec 3×2 min allure course. Vérifier le matériel.", 45, "Z2"),
        SessionSpec(4, Sport.REST, "Repos", "Repos, préparer le sac et le parcours de transition.", 0),
        SessionSpec(5, Sport.BRICK, "Activation veille de course", "20 min vélo + 10 min course avec 3 accélérations.", 30, "Z2"),
        SessionSpec(
            6,
            Sport.RACE,
            "Triathlon M",
            "1,5 km natation / 40 km vélo / 10 km course. Partir prudemment, gérer l'effort, s'alimenter sur le vélo.",
            150,
            "Course",
        ),
    ]


def generate_plan(race_date: date, peak_hours: float, today: date | None = None) -> Plan:
    today = today or date.today()
    if peak_hours <= 0:
        raise ValueError("Le volume hebdomadaire doit être positif.")
    weeks = build_weeks(race_date, today)
    plan = Plan(race_date=race_date, weeks=weeks)
    for i, wk in enumerate(weeks):
        for s in week_sessions(wk, peak_hours, is_last=i == len(weeks) - 1):
            plan.sessions.append(
                PlannedSession(
                    date=wk.start + timedelta(days=s.offset),
                    week=wk.week,
                    phase=wk.phase,
                    recovery_week=wk.recovery,
                    sport=s.sport,
                    title=s.title,
                    description=s.description,
                    duration_min=s.duration_min,
                    intensity=s.intensity,
                )
            )
    return plan
