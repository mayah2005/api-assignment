from typing import Any

from cs188_a3 import external
from flask.testing import FlaskClient

PASSWORD = "cs188test"

FAKE_CHARACTERS: dict[str, dict[str, Any]] = {
    "albedo": {"vision": "Geo", "weapon": "Sword", "rarity": 5},
    "diluc": {"vision": "Pyro", "weapon": "Claymore", "rarity": 5},
    "xingqiu": {"vision": "Hydro", "weapon": "Sword", "rarity": 4},
}

FAKE_ELEMENTS: dict[str, dict[str, Any]] = {
    "geo": {
        "name": "Geo",
        "reactions": [
            {"name": "Crystallize", "elements": ["Pyro", "Hydro"],
             "description": "Geo meets another element."},
        ],
    },
    "pyro": {
        "name": "Pyro",
        "reactions": [
            {"name": "Vaporize", "elements": ["Hydro"], "description": "Pyro meets Hydro."},
            {"name": "Overloaded", "elements": ["Electro"], "description": "Pyro meets Electro."},
        ],
    },
    "hydro": {
        "name": "Hydro",
        "reactions": [
            {"name": "Vaporize", "elements": ["Pyro"], "description": "Hydro meets Pyro."},
        ],
    },
}

class FakeGenshin:
    def __init__(self) -> None:
        self.down = False
        self.calls: list[str] = []

    def _lookup(self, table: dict[str, dict[str, Any]], slug: str) -> dict[str, Any]:
        self.calls.append(slug)
        if self.down:
            raise external.ExternalServiceUnavailable("simulated outage")
        if slug not in table:
            raise external.EntityNotFound(slug)
        return table[slug]

    def fetch_character(self, slug: str) -> dict[str, Any]:
        return self._lookup(FAKE_CHARACTERS, slug)

    def fetch_element(self, slug: str) -> dict[str, Any]:
        return self._lookup(FAKE_ELEMENTS, slug)

def make_user(client: FlaskClient, name: str = "maya") -> tuple[str, str]:
    response = client.post("/register", json={"username": name, "password": PASSWORD})
    assert response.status_code == 201
    return (name, PASSWORD)

def make_entry(
    client: FlaskClient, auth: tuple[str, str], **overrides: Any
) -> dict[str, Any]:
    body = {"character": "albedo", "level": 80, "constellation": 0,
            "role": "sub_dps", **overrides}
    response = client.post("/roster", json=body, auth=auth)
    assert response.status_code == 201, response.json
    return response.json

def make_team(
    client: FlaskClient, auth: tuple[str, str], member_ids: list[int],
    name: str = "Test Team",
) -> dict[str, Any]:
    response = client.post("/teams", json={"name": name, "members": member_ids}, auth=auth)
    assert response.status_code == 201, response.json
    return response.json