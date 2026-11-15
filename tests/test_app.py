import html
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.stats import pace_label


@pytest.fixture
def client():
    with TestClient(create_app("sqlite://")) as c:
        yield c


def race_in(weeks: int) -> str:
    return (date.today() + timedelta(weeks=weeks)).isoformat()


def configure(client, weeks=12, hours=8):
    return client.post(
        "/settings",
        data={"race_name": "Tri de test", "race_date": race_in(weeks), "peak_hours": hours},
        follow_redirects=False,
    )


def test_pages_render_without_plan(client):
    for path in ["/", "/plan", "/journal", "/progress", "/settings"]:
        r = client.get(path)
        assert r.status_code == 200, path
    assert "Configurer mon objectif" in client.get("/").text


def test_pwa_assets(client):
    assert client.get("/manifest.webmanifest").json()["short_name"] == "Tri M"
    sw = client.get("/sw.js")
    assert sw.status_code == 200
    assert "javascript" in sw.headers["content-type"]


def test_settings_generate_plan(client):
    r = configure(client)
    assert r.status_code == 303
    page = client.get("/plan").text
    assert "S12" in page
    assert "Triathlon M" in page
    assert "Tri de test" in client.get("/").text


def test_settings_rejects_too_close_race(client):
    r = client.post(
        "/settings",
        data={"race_name": "x", "race_date": race_in(1), "peak_hours": 8},
    )
    assert r.status_code == 200
    assert "au moins" in r.text


def test_log_session_and_stats(client):
    configure(client)
    r = client.post(
        "/journal",
        data={"date": date.today().isoformat(), "sport": "run", "duration_min": 45, "distance_km": "9,0", "rpe": 6},
        headers={"HX-Request": "true"},
    )
    assert r.status_code == 204
    assert r.headers["HX-Refresh"] == "true"

    journal = html.unescape(client.get("/journal").text)
    assert "Course à pied" in journal
    assert "5'00/km" in journal

    weekly = client.get("/api/stats/weekly").json()
    assert sum(w["run"] for w in weekly) == 45
    assert any(w["planned"] > 0 for w in weekly)


def test_validate_planned_session_and_regenerate_keeps_link(client):
    configure(client, weeks=12)
    form = client.get("/journal/form?planned_id=2").text
    assert 'name="planned_id" value="2"' in form

    client.post(
        "/journal",
        data={"date": race_in(0), "sport": "swim", "duration_min": 40, "planned_id": "2"},
    )
    assert "✓" in client.get("/plan").text

    configure(client, weeks=12, hours=10)  # régénération avec un autre volume
    assert "✓" in client.get("/plan").text


def test_delete_log(client):
    client.post("/journal", data={"date": date.today().isoformat(), "sport": "bike", "duration_min": 60})
    assert "Vélo" in client.get("/journal").text
    assert client.delete("/journal/1").status_code == 200
    assert client.delete("/journal/1").status_code == 404


def test_invalid_log_rejected(client):
    r = client.post("/journal", data={"date": date.today().isoformat(), "sport": "run", "duration_min": 0})
    assert r.status_code == 422


@pytest.mark.parametrize(
    ("sport", "minutes", "km", "expected"),
    [
        ("swim", 30, 1.5, "2'00/100 m"),
        ("bike", 60, 30, "30.0 km/h"),
        ("run", 50, 10, "5'00/km"),
        ("run", 50, None, ""),
    ],
)
def test_pace_label(sport, minutes, km, expected):
    assert pace_label(sport, minutes, km) == expected
