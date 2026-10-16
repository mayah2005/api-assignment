import sqlite3
from contextlib import closing

import pytest
from flask import Flask
from flask.testing import FlaskClient
from helpers import PASSWORD, make_user

PROTECTED_ROUTES = [
    ("post", "/roster"),
    ("patch", "/roster/1"),
    ("delete", "/roster/1"),
    ("post", "/teams"),
    ("delete", "/teams/1"),
]

def test_register_success(client: FlaskClient) -> None:
    response = client.post("/register", json={"username": "maya", "password": PASSWORD})
    assert response.status_code == 201
    assert isinstance(response.json["id"], int)

def test_register_response_never_contains_password(client: FlaskClient) -> None:
    response = client.post("/register", json={"username": "maya", "password": PASSWORD})
    assert PASSWORD not in response.get_data(as_text=True)

def test_register_duplicate_username_returns_409(client: FlaskClient) -> None:
    make_user(client)
    response = client.post("/register", json={"username": "maya", "password": PASSWORD})
    assert response.status_code == 409
    assert response.json["message"]

@pytest.mark.parametrize(
    "body",
    [
        {},
        {"username": "maya"},
        {"password": PASSWORD},
        {"username": "", "password": PASSWORD},
        {"username": "   ", "password": PASSWORD},
        {"username": "maya", "password": ""},
        {"username": "maya", "password": "        "},
        {"username": "maya", "password": "short"},
        {"username": "maya", "password": "x" * 73},
        {"username": "a" * 51, "password": PASSWORD},
        {"username": 123, "password": PASSWORD},
        {"username": ["maya"], "password": PASSWORD},
        {"username": "maya", "password": 12345678},
    ],
)
def test_register_rejects_invalid_fields(client: FlaskClient, body: dict) -> None:
    response = client.post("/register", json=body)
    assert response.status_code == 400
    assert response.json["message"]

@pytest.mark.parametrize(
    ("data", "content_type"),
    [
        ("not json", "application/json"),
        ("[1, 2]", "application/json"),
        ("null", "application/json"),
        ("", "application/json"),
        ('{"username": "maya", "password": "hunter2hunter2"}', "text/plain"),
    ],
)
def test_register_rejects_non_object_body(
    client: FlaskClient, data: str, content_type: str
) -> None:
    response = client.post("/register", data=data, content_type=content_type)
    assert response.status_code == 400
    assert response.json["message"]

def test_password_is_stored_as_hash(app: Flask, client: FlaskClient) -> None:
    make_user(client)
    with closing(sqlite3.connect(app.config["DB_PATH"])) as conn:
        stored = conn.execute("SELECT password FROM users").fetchone()[0]
    assert stored != PASSWORD
    assert stored.startswith("$2")  # bcrypt hashes begin with $2b$


def test_sql_metacharacters_in_username_are_stored_literally(client: FlaskClient) -> None:
    auth = make_user(client, "bob'; DROP TABLE users; --")
    make_user(client, "carol")  # the users table still exists
    assert client.delete("/roster/1", auth=auth).status_code == 404

@pytest.mark.parametrize(("method", "path"), PROTECTED_ROUTES)
def test_protected_route_requires_credentials(
    client: FlaskClient, method: str, path: str
) -> None:
    response = getattr(client, method)(path)
    assert response.status_code == 401
    assert response.json["message"]

@pytest.mark.parametrize(("method", "path"), PROTECTED_ROUTES)
def test_protected_route_rejects_wrong_password(
    client: FlaskClient, method: str, path: str
) -> None:
    make_user(client)
    response = getattr(client, method)(path, auth=("maya", "wrongpassword"))
    assert response.status_code == 401


def test_non_basic_authorization_scheme_is_rejected(client: FlaskClient) -> None:
    response = client.delete("/roster/1", headers={"Authorization": "Bearer abc123"})
    assert response.status_code == 401

def test_unknown_user_and_wrong_password_look_identical(client: FlaskClient) -> None:
    make_user(client)
    wrong_password = client.delete("/roster/1", auth=("maya", "wrongpassword"))
    unknown_user = client.delete("/roster/1", auth=("nobody", PASSWORD))
    assert wrong_password.status_code == unknown_user.status_code == 401
    assert wrong_password.json == unknown_user.json

def test_valid_credentials_are_accepted(client: FlaskClient) -> None:
    auth = make_user(client)
    assert client.delete("/roster/1", auth=auth).status_code == 404