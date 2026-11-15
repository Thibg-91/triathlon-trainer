from datetime import date, timedelta

import pytest

from app.models import Phase, Sport
from app.plan import MAX_WEEKS, generate_plan, phase_split

TODAY = date(2026, 11, 16)


def training_minutes(plan, week):
    return sum(
        s.duration_min for s in plan.sessions if s.week == week and s.sport not in (Sport.REST, Sport.RACE)
    )


def test_plan_ends_with_race_on_race_day():
    race = TODAY + timedelta(weeks=12)
    plan = generate_plan(race, 8, today=TODAY)
    last = max(plan.sessions, key=lambda s: s.date)
    assert last.date == race
    assert last.sport is Sport.RACE


def test_plan_is_capped_and_starts_after_today():
    race = TODAY + timedelta(weeks=40)
    plan = generate_plan(race, 8, today=TODAY)
    assert len(plan.weeks) == MAX_WEEKS
    assert plan.start_date >= TODAY
    assert plan.start_date + timedelta(days=7 * MAX_WEEKS - 1) == race


def test_too_short_raises():
    with pytest.raises(ValueError):
        generate_plan(TODAY + timedelta(days=10), 8, today=TODAY)


@pytest.mark.parametrize("n", range(3, MAX_WEEKS + 1))
def test_phase_split_sums_to_n(n):
    split = phase_split(n)
    assert sum(split.values()) == n
    assert split[Phase.TAPER] >= 1


def test_phases_are_in_order():
    plan = generate_plan(TODAY + timedelta(weeks=16), 8, today=TODAY)
    order = [Phase.BASE, Phase.BUILD, Phase.PEAK, Phase.TAPER]
    ranks = [order.index(w.phase) for w in plan.weeks]
    assert ranks == sorted(ranks)


def test_peak_week_matches_target_volume():
    plan = generate_plan(TODAY + timedelta(weeks=16), 8, today=TODAY)
    peak = next(w for w in plan.weeks if w.phase is Phase.PEAK)
    # arrondis à 5 min près sur 7 séances
    assert abs(training_minutes(plan, peak.week) - 8 * 60) <= 20


def test_recovery_weeks_are_lighter():
    plan = generate_plan(TODAY + timedelta(weeks=16), 8, today=TODAY)
    for w in plan.weeks:
        if w.recovery:
            assert training_minutes(plan, w.week) < training_minutes(plan, w.week - 1)


def test_every_week_has_each_discipline_and_a_rest_day():
    plan = generate_plan(TODAY + timedelta(weeks=12), 7, today=TODAY)
    for w in plan.weeks:
        sports = {s.sport for s in plan.sessions if s.week == w.week}
        assert {Sport.SWIM, Sport.BIKE, Sport.RUN, Sport.REST} <= sports or Sport.RACE in sports


def test_bricks_only_in_build_and_peak():
    plan = generate_plan(TODAY + timedelta(weeks=16), 8, today=TODAY)
    bricks = [s for s in plan.sessions if s.sport is Sport.BRICK and s.week != len(plan.weeks)]
    assert bricks
    assert all(s.phase in (Phase.BUILD, Phase.PEAK) for s in bricks)


def test_volume_scales_with_peak_hours():
    race = TODAY + timedelta(weeks=12)
    small = generate_plan(race, 5, today=TODAY)
    big = generate_plan(race, 10, today=TODAY)
    assert training_minutes(big, 1) > training_minutes(small, 1)
