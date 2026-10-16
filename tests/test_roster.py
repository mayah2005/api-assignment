"""Tests for the /roster endpoints."""
import pytest
from flask.testing import FlaskClient

from helpers import FakeGenshin, make_entry

VALID_BODY = {"character": "albedo", "level": 80, "constellation": 0, "role": "sub_dps"}

# (field, bad value) pairs, used for both POST and PATCH
INVALID_FIELD_VALUES = [
    ("level", 0), ("level", 91), ("level", 2**64), ("level", "80"),
    ("level", 80.5), ("level", True), ("level", None),
    ("constellation", -1), ("constellation", 7), ("constellation", "1"),
    ("role", "tank"), ("role", 5), ("role", ["main_dps"]), ("role", None),
    ("character", ""), ("character", "   "), ("character", 123),
    ("character", "has space"), ("character", "Bad_Slug!"),
    ("character", "a" * 61), ("character", None),
    ("nickname", "   "), ("nickname", 123), ("nickname", "x" * 41),
    ("notes", 123), ("notes", "x" * 501),
    # server-controlled or unrecognized fields must be rejected, not ignored
    ("id", 99), ("owner_id", 2), ("created_at", "2000-01-01T00:00:00"),
    ("vision", "Pyro"),
]

NOT_JSON_OBJECTS = [
    ("not json", "application/json"),
    ("[1, 2]", "application/json"),
    ("null", "application/json"),
    ("", "application/json"),
    ('{"level": 85}', "text/plain"),
]

# Ids that should never match a record: zero, negative, non-numeric, huge
BAD_IDS = ["0", "-1", "abc", "1.5", "99999", str(2**63 - 1), str(2**63), str(2**100)]


def _without(key: str) -> dict:
    """VALID_BODY with one required field removed."""
    return {k: v for k, v in VALID_BODY.items() if k != key}


# ---------- Create ----------

def test_create_entry_happy_path(client: FlaskClient, maya: tuple[str, str]) -> None:
    """POST creates a record, fills server fields, and sets Location."""
    body = {**VALID_BODY, "nickname": "Al", "notes": "Carry"}
    response = client.post("/roster", json=body, auth=maya)
    assert response.status_code == 201
    entry = response.json
    assert entry["character"] == "albedo"
    assert entry["nickname"] == "Al"
    assert entry["notes"] == "Carry"
    # these come from the (fake) external API, not the request
    assert (entry["vision"], entry["weapon_type"], entry["rarity"]) == ("Geo", "Sword", 5)
    assert isinstance(entry["id"], int)
    assert isinstance(entry["owner_id"], int)
    assert entry["created_at"]
    assert response.headers["Location"].endswith(f"/roster/{entry['id']}")
    assert client.get(f"/roster/{entry['id']}").json == entry


def test_create_defaults_optional_fields_to_none(
    client: FlaskClient, maya: tuple[str, str]
) -> None:
    """nickname and notes are optional."""
    entry = make_entry(client, maya)
    assert entry["nickname"] is None
    assert entry["notes"] is None


def test_create_normalizes_character_to_lowercase(
    client: FlaskClient, maya: tuple[str, str]
) -> None:
    """'Albedo' is stored as the slug 'albedo'."""
    assert make_entry(client, maya, character="Albedo")["character"] == "albedo"


@pytest.mark.parametrize("body", [_without(key) for key in VALID_BODY])
def test_create_rejects_missing_required_field(
    client: FlaskClient, maya: tuple[str, str], body: dict
) -> None:
    """Each required field is actually required."""
    response = client.post("/roster", json=body, auth=maya)
    assert response.status_code == 400
    assert response.json["message"]


@pytest.mark.parametrize(("field", "value"), INVALID_FIELD_VALUES)
def test_create_rejects_invalid_values(
    client: FlaskClient, maya: tuple[str, str], field: str, value: object
) -> None:
    """Wrong types, out-of-range values, and unrecognized fields give 400."""
    response = client.post("/roster", json={**VALID_BODY, field: value}, auth=maya)
    assert response.status_code == 400
    assert response.json["message"]
    assert client.get("/roster").json == []  # nothing was stored


@pytest.mark.parametrize(("data", "content_type"), NOT_JSON_OBJECTS)
def test_create_rejects_non_object_body(
    client: FlaskClient, maya: tuple[str, str], data: str, content_type: str
) -> None:
    """A body that isn't a JSON object gives 400."""
    response = client.post("/roster", data=data, content_type=content_type, auth=maya)
    assert response.status_code == 400
    assert response.json["message"]


def test_create_unknown_character_returns_400(
    client: FlaskClient, maya: tuple[str, str]
) -> None:
    """A character the external API doesn't know is the caller's mistake (400)."""
    response = client.post(
        "/roster", json={**VALID_BODY, "character": "notarealperson"}, auth=maya)
    assert response.status_code == 400
    assert "notarealperson" in response.json["message"]
    assert client.get("/roster").json == []


def test_create_returns_502_when_external_api_is_down(
    client: FlaskClient, maya: tuple[str, str], fake_genshin: FakeGenshin
) -> None:
    """An external outage is a 502 with a JSON message, and nothing is stored."""
    fake_genshin.down = True
    response = client.post("/roster", json=VALID_BODY, auth=maya)
    assert response.status_code == 502
    assert response.json["message"]
    assert client.get("/roster").json == []


# ---------- Read ----------

def test_get_entry_needs_no_auth(client: FlaskClient, maya: tuple[str, str]) -> None:
    """Anyone can read a single record."""
    entry = make_entry(client, maya)
    response = client.get(f"/roster/{entry['id']}")
    assert response.status_code == 200
    assert response.json == entry


@pytest.mark.parametrize("bad_id", BAD_IDS)
def test_get_nonexistent_or_malformed_id_returns_404(client: FlaskClient, bad_id: str) -> None:
    """Zero, negative, non-numeric, and huge ids all give a JSON 404."""
    response = client.get(f"/roster/{bad_id}")
    assert response.status_code == 404
    assert response.json["message"]


def test_list_empty(client: FlaskClient) -> None:
    """An empty database lists as an empty array."""
    response = client.get("/roster")
    assert response.status_code == 200
    assert response.json == []


@pytest.fixture
def three_entries(client: FlaskClient, maya: tuple[str, str]) -> None:
    """Create albedo (lvl 90), diluc (lvl 40), and xingqiu (lvl 70) as maya."""
    make_entry(client, maya, character="albedo", level=90, role="sub_dps")
    make_entry(client, maya, character="diluc", level=40, role="main_dps")
    make_entry(client, maya, character="xingqiu", level=70, role="support")


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("", ["albedo", "diluc", "xingqiu"]),
        ("role=main_dps", ["diluc"]),
        ("vision=geo", ["albedo"]),
        ("vision=PYRO", ["diluc"]),  # filter is case-insensitive
        ("vision=anemo", []),
        ("min_level=70", ["albedo", "xingqiu"]),
        ("role=main_dps&min_level=70", []),
        ("limit=2", ["albedo", "diluc"]),
        ("limit=1&offset=1", ["diluc"]),
        ("offset=2", ["xingqiu"]),
        ("offset=3", []),
    ],
)
@pytest.mark.usefixtures("three_entries")
def test_list_filters_and_paging(client: FlaskClient, query: str, expected: list[str]) -> None:
    """Filters and paging return the expected records, in id order."""
    response = client.get(f"/roster?{query}")
    assert response.status_code == 200
    assert [entry["character"] for entry in response.json] == expected


@pytest.mark.parametrize(
    "query",
    ["role=tank", "min_level=abc", "min_level=", "min_level=0", "min_level=91",
     "limit=0", "limit=101", "limit=abc", "offset=-1", "offset=abc",
     f"offset={2**63}"],
)
def test_list_rejects_bad_query_parameters(client: FlaskClient, query: str) -> None:
    """Invalid filter or paging parameters give 400 with a message."""
    response = client.get(f"/roster?{query}")
    assert response.status_code == 400
    assert response.json["message"]


# ---------- Update ----------

def test_patch_changes_only_given_fields(client: FlaskClient, maya: tuple[str, str]) -> None:
    """PATCH updates the fields present and leaves the rest alone."""
    entry = make_entry(client, maya, nickname="Al", notes="keep me")
    response = client.patch(f"/roster/{entry['id']}", json={"level": 85}, auth=maya)
    assert response.status_code == 200
    assert response.json == {**entry, "level": 85}


def test_patch_can_clear_optional_field(client: FlaskClient, maya: tuple[str, str]) -> None:
    """Sending null for nickname removes it."""
    entry = make_entry(client, maya, nickname="Al")
    response = client.patch(f"/roster/{entry['id']}", json={"nickname": None}, auth=maya)
    assert response.status_code == 200
    assert response.json["nickname"] is None


def test_patch_character_refreshes_external_details(
    client: FlaskClient, maya: tuple[str, str]
) -> None:
    """Changing the character re-fetches vision, weapon type, and rarity."""
    entry = make_entry(client, maya, character="albedo")
    response = client.patch(f"/roster/{entry['id']}", json={"character": "diluc"}, auth=maya)
    assert response.status_code == 200
    assert (response.json["vision"], response.json["weapon_type"]) == ("Pyro", "Claymore")


def test_patch_without_character_change_skips_external_api(
    client: FlaskClient, maya: tuple[str, str], fake_genshin: FakeGenshin
) -> None:
    """Editing other fields works even while the external API is down."""
    entry = make_entry(client, maya)
    fake_genshin.calls.clear()
    fake_genshin.down = True
    response = client.patch(f"/roster/{entry['id']}", json={"level": 10}, auth=maya)
    assert response.status_code == 200
    assert fake_genshin.calls == []


def test_patch_character_returns_502_when_external_api_is_down(
    client: FlaskClient, maya: tuple[str, str], fake_genshin: FakeGenshin
) -> None:
    """Changing the character during an outage fails cleanly and changes nothing."""
    entry = make_entry(client, maya)
    fake_genshin.down = True
    response = client.patch(f"/roster/{entry['id']}", json={"character": "diluc"}, auth=maya)
    assert response.status_code == 502
    assert client.get(f"/roster/{entry['id']}").json == entry


def test_patch_empty_body_returns_400(client: FlaskClient, maya: tuple[str, str]) -> None:
    """A PATCH with nothing to change is a client error."""
    entry = make_entry(client, maya)
    response = client.patch(f"/roster/{entry['id']}", json={}, auth=maya)
    assert response.status_code == 400
    assert response.json["message"]


@pytest.mark.parametrize(("field", "value"), INVALID_FIELD_VALUES)
def test_patch_rejects_invalid_values(
    client: FlaskClient, maya: tuple[str, str], field: str, value: object
) -> None:
    """The same validation applies to updates, and the record stays unchanged."""
    entry = make_entry(client, maya)
    response = client.patch(f"/roster/{entry['id']}", json={field: value}, auth=maya)
    assert response.status_code == 400
    assert response.json["message"]
    assert client.get(f"/roster/{entry['id']}").json == entry


@pytest.mark.parametrize(("data", "content_type"), NOT_JSON_OBJECTS)
def test_patch_rejects_non_object_body(
    client: FlaskClient, maya: tuple[str, str], data: str, content_type: str
) -> None:
    """A PATCH body that isn't a JSON object gives 400."""
    entry = make_entry(client, maya)
    response = client.patch(
        f"/roster/{entry['id']}", data=data, content_type=content_type, auth=maya)
    assert response.status_code == 400


@pytest.mark.parametrize("bad_id", BAD_IDS)
def test_patch_nonexistent_or_malformed_id_returns_404(
    client: FlaskClient, maya: tuple[str, str], bad_id: str
) -> None:
    """Updating a record that doesn't exist is a 404."""
    response = client.patch(f"/roster/{bad_id}", json={"level": 5}, auth=maya)
    assert response.status_code == 404


# ---------- Delete ----------

def test_delete_entry(client: FlaskClient, maya: tuple[str, str]) -> None:
    """DELETE removes the record; a second DELETE is a 404."""
    entry = make_entry(client, maya)
    assert client.delete(f"/roster/{entry['id']}", auth=maya).status_code == 204
    assert client.get(f"/roster/{entry['id']}").status_code == 404
    assert client.delete(f"/roster/{entry['id']}", auth=maya).status_code == 404


@pytest.mark.parametrize("bad_id", BAD_IDS)
def test_delete_nonexistent_or_malformed_id_returns_404(
    client: FlaskClient, maya: tuple[str, str], bad_id: str
) -> None:
    """Deleting a record that doesn't exist is a 404."""
    assert client.delete(f"/roster/{bad_id}", auth=maya).status_code == 404


# ---------- Ownership ----------

def test_other_user_can_read_but_not_change_or_delete(
    client: FlaskClient, maya: tuple[str, str], bob: tuple[str, str]
) -> None:
    """Bob can read maya's record, but PATCH and DELETE give 403 and change nothing."""
    entry = make_entry(client, maya)
    path = f"/roster/{entry['id']}"
    assert client.get(path, auth=bob).json == entry

    patch = client.patch(path, json={"level": 1}, auth=bob)
    assert patch.status_code == 403
    assert patch.json["message"]

    delete = client.delete(path, auth=bob)
    assert delete.status_code == 403
    assert delete.json["message"]

    assert client.get(path).json == entry  # still there and unchanged


def test_owner_is_the_authenticated_user_not_the_body(
    client: FlaskClient, maya: tuple[str, str], bob: tuple[str, str]
) -> None:
    """Each user's records belong to them: bob can't edit maya's, but can edit his own."""
    mayas = make_entry(client, maya)
    bobs = make_entry(client, bob)
    assert mayas["owner_id"] != bobs["owner_id"]
    assert client.patch(f"/roster/{bobs['id']}", json={"level": 5}, auth=bob).status_code == 200
    assert client.patch(f"/roster/{mayas['id']}", json={"level": 5}, auth=bob).status_code == 403