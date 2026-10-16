from collections.abc import Iterator
from pathlib import Path

import pytest
from cs188_a3 import create_app, external, services
from cs188_a3.db import Database
from flask import Flask
from flask.testing import FlaskClient
from helpers import FakeGenshin, make_user


@pytest.fixture(autouse=True)
def fast_password_hashing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(services._bcrypt, "_log_rounds", 4, raising=False)

@pytest.fixture
def fake_genshin(monkeypatch: pytest.MonkeyPatch) -> FakeGenshin:
    fake = FakeGenshin()
    monkeypatch.setattr(external, "fetch_character", fake.fetch_character)
    monkeypatch.setattr(external, "fetch_element", fake.fetch_element)
    return fake

@pytest.fixture
def app(tmp_path: Path, fake_genshin: FakeGenshin) -> Flask:
    app = create_app(db_path=tmp_path / "test.db")
    app.testing = True
    return app

@pytest.fixture
def client(app: Flask) -> Iterator[FlaskClient]:
    with app.test_client() as client:
        yield client

@pytest.fixture
def db(tmp_path: Path, fake_genshin: FakeGenshin) -> Iterator[Database]:
    database = Database(tmp_path / "services.db")
    yield database
    database.conn.close()

@pytest.fixture
def maya(client: FlaskClient) -> tuple[str, str]:
    return make_user(client, "maya")

@pytest.fixture
def stuart(client: FlaskClient) -> tuple[str, str]:
    return make_user(client, "stuart")

@pytest.fixture
def live_client(tmp_path: Path) -> Iterator[FlaskClient]:
    """A test client whose external API calls go to the real service."""
    app = create_app(db_path=tmp_path / "live.db")
    app.testing = True
    with app.test_client() as client:
        yield client