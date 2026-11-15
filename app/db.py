"""Connexion base de données."""
from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

DEFAULT_DB_URL = "sqlite:///./data/triathlon.db"


def make_engine(url: str | None = None):
    url = url or os.environ.get("TRI_DB_URL", DEFAULT_DB_URL)
    kwargs: dict = {}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
        if url in ("sqlite://", "sqlite:///:memory:"):
            kwargs["poolclass"] = StaticPool  # base mémoire partagée (tests)
        else:
            path = url.removeprefix("sqlite:///")
            Path(path).parent.mkdir(parents=True, exist_ok=True)
    return create_engine(url, **kwargs)


def init_db(engine) -> None:
    SQLModel.metadata.create_all(engine)


def session_factory(engine):
    def get_session() -> Iterator[Session]:
        with Session(engine) as session:
            yield session

    return get_session
