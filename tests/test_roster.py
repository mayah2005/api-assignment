import pytest
from flask.testing import FlaskClient
from helpers import BAD_IDS, NOT_JSON_OBJECTS, FakeGenshin, make_entry

VALID_BODY = {"character": "albedo", "level": 80, "constellation": 0, "role": "sub_dps"}

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

def _without(key: str) -> dict:
    return {k: v for k, v in VALID_BODY.items() if k != key}

def test_create_entry_happy_path(client: FlaskClient, maya: tuple[str, str]) -> None:
    body = {**VALID_BODY, "nickname": "Al", "notes": "Carry"}
    response = client.post("/roster", json=body, auth=maya)
    assert response.status_code == 201
    entry = response.json
    assert entry["character"] == "albedo"
    assert entry["nickname"] == "Al"
    assert entry["notes"] == "Carry"
    assert (entry["vision"], entry["weapon_type"], entry["rarity"]) == ("Geo", "Sword", 5)
    assert isinstance(entry["id"], int)
    assert isinstance(entry["owner_id"], int)
    assert entry["created_at"]
    assert response.headers["Location"].endswith(f"/roster/{entry['id']}")
    assert client.get(f"/roster/{entry['id']}").json == entry


def test_create_defaults_optional_fields_to_none(
    client: FlaskClient, maya: tuple[str, str]
) -> None:
    entry = make_entry(client, maya)
    assert entry["nickname"] is None
    assert entry["notes"] is None

def test_create_normalizes_character_to_lowercase(
    client: FlaskClient, maya: tuple[str, str]
) -> None:
    assert make_entry(client, maya, character="Albedo")["character"] == "albedo"

@pytest.mark.parametrize("body", [_without(key) for key in VALID_BODY])
def test_create_rejects_missing_required_field(
    client: FlaskClient, maya: tuple[str, str], body: dict
) -> None:
    response = client.post("/roster", json=body, auth=maya)
    assert response.status_code == 400
    assert response.json["message"]

@pytest.mark.parametrize(("field", "value"), INVALID_FIELD_VALUES)
def test_create_rejects_invalid_values(
    client: FlaskClient, maya: tuple[str, str], field: str, value: object
) -> None:
    response = client.post("/roster", json={**VALID_BODY, field: value}, auth=maya)
    assert response.status_code == 400
    assert response.json["message"]
    assert client.get("/roster").json == []  # nothing was stored

@pytest.mark.parametrize(("data", "content_type"), NOT_JSON_OBJECTS)
def test_create_rejects_non_object_body(
    client: FlaskClient, maya: tuple[str, str], data: str, content_type: str
) -> None:
    response = client.post("/roster", data=data, content_type=content_type, auth=maya)
    assert response.status_code == 400
    assert response.json["message"]

def test_create_unknown_character_returns_400(
    client: FlaskClient, maya: tuple[str, str]
) -> None:
    response = client.post(
        "/roster", json={**VALID_BODY, "character": "notarealperson"}, auth=maya)
    assert response.status_code == 400
    assert "notarealperson" in response.json["message"]
    assert client.get("/roster").json == []

def test_create_returns_502_when_external_api_is_down(
    client: FlaskClient, maya: tuple[str, str], fake_genshin: FakeGenshin
) -> None:
    fake_genshin.down = True
    response = client.post("/roster", json=VALID_BODY, auth=maya)
    assert response.status_code == 502
    assert response.json["message"]
    assert client.get("/roster").json == []

def test_get_entry_needs_no_auth(client: FlaskClient, maya: tuple[str, str]) -> None:
    entry = make_entry(client, maya)
    response = client.get(f"/roster/{entry['id']}")
    assert response.status_code == 200
    assert response.json == entry

@pytest.mark.parametrize("bad_id", BAD_IDS)
def test_get_nonexistent_or_malformed_id_returns_404(client: FlaskClient, bad_id: str) -> None:
    response = client.get(f"/roster/{bad_id}")
    assert response.status_code == 404
    assert response.json["message"]

def test_list_empty(client: FlaskClient) -> None:
    response = client.get("/roster")
    assert response.status_code == 200
    assert response.json == []

@pytest.fixture
def three_entries(client: FlaskClient, maya: tuple[str, str]) -> None:
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
    response = client.get(f"/roster?{query}")
    assert response.status_code == 400
    assert response.json["message"]

def test_patch_changes_only_given_fields(client: FlaskClient, maya: tuple[str, str]) -> None:
    entry = make_entry(client, maya, nickname="Al", notes="keep me")
    response = client.patch(f"/roster/{entry['id']}", json={"level": 85}, auth=maya)
    assert response.status_code == 200
    assert response.json == {**entry, "level": 85}

def test_patch_can_clear_optional_field(client: FlaskClient, maya: tuple[str, str]) -> None:
    entry = make_entry(client, maya, nickname="Al")
    response = client.patch(f"/roster/{entry['id']}", json={"nickname": None}, auth=maya)
    assert response.status_code == 200
    assert response.json["nickname"] is None

def test_patch_character_refreshes_external_details(
    client: FlaskClient, maya: tuple[str, str]
) -> None:
    entry = make_entry(client, maya, character="albedo")
    response = client.patch(f"/roster/{entry['id']}", json={"character": "diluc"}, auth=maya)
    assert response.status_code == 200
    assert (response.json["vision"], response.json["weapon_type"]) == ("Pyro", "Claymore")

def test_patch_without_character_change_skips_external_api(
    client: FlaskClient, maya: tuple[str, str], fake_genshin: FakeGenshin
) -> None:
    entry = make_entry(client, maya)
    fake_genshin.calls.clear()
    fake_genshin.down = True
    response = client.patch(f"/roster/{entry['id']}", json={"level": 10}, auth=maya)
    assert response.status_code == 200
    assert fake_genshin.calls == []

def test_patch_character_returns_502_when_external_api_is_down(
    client: FlaskClient, maya: tuple[str, str], fake_genshin: FakeGenshin
) -> None:
    entry = make_entry(client, maya)
    fake_genshin.down = True
    response = client.patch(f"/roster/{entry['id']}", json={"character": "diluc"}, auth=maya)
    assert response.status_code == 502
    assert client.get(f"/roster/{entry['id']}").json == entry

def test_patch_empty_body_returns_400(client: FlaskClient, maya: tuple[str, str]) -> None:
    entry = make_entry(client, maya)
    response = client.patch(f"/roster/{entry['id']}", json={}, auth=maya)
    assert response.status_code == 400
    assert response.json["message"]

@pytest.mark.parametrize(("field", "value"), INVALID_FIELD_VALUES)
def test_patch_rejects_invalid_values(
    client: FlaskClient, maya: tuple[str, str], field: str, value: object
) -> None:
    entry = make_entry(client, maya)
    response = client.patch(f"/roster/{entry['id']}", json={field: value}, auth=maya)
    assert response.status_code == 400
    assert response.json["message"]
    assert client.get(f"/roster/{entry['id']}").json == entry

@pytest.mark.parametrize(("data", "content_type"), NOT_JSON_OBJECTS)
def test_patch_rejects_non_object_body(
    client: FlaskClient, maya: tuple[str, str], data: str, content_type: str
) -> None:
    entry = make_entry(client, maya)
    response = client.patch(
        f"/roster/{entry['id']}", data=data, content_type=content_type, auth=maya)
    assert response.status_code == 400

@pytest.mark.parametrize("bad_id", BAD_IDS)
def test_patch_nonexistent_or_malformed_id_returns_404(
    client: FlaskClient, maya: tuple[str, str], bad_id: str
) -> None:
    response = client.patch(f"/roster/{bad_id}", json={"level": 5}, auth=maya)
    assert response.status_code == 404


# ---------- Delete ----------

def test_delete_entry(client: FlaskClient, maya: tuple[str, str]) -> None:
    entry = make_entry(client, maya)
    assert client.delete(f"/roster/{entry['id']}", auth=maya).status_code == 204
    assert client.get(f"/roster/{entry['id']}").status_code == 404
    assert client.delete(f"/roster/{entry['id']}", auth=maya).status_code == 404


@pytest.mark.parametrize("bad_id", BAD_IDS)
def test_delete_nonexistent_or_malformed_id_returns_404(
    client: FlaskClient, maya: tuple[str, str], bad_id: str
) -> None:
    assert client.delete(f"/roster/{bad_id}", auth=maya).status_code == 404

def test_other_user_can_read_but_not_change_or_delete(
    client: FlaskClient, maya: tuple[str, str], stuart: tuple[str, str]
) -> None:
    entry = make_entry(client, maya)
    path = f"/roster/{entry['id']}"
    assert client.get(path, auth=stuart).json == entry

    patch = client.patch(path, json={"level": 1}, auth=stuart)
    assert patch.status_code == 403
    assert patch.json["message"]

    delete = client.delete(path, auth=stuart)
    assert delete.status_code == 403
    assert delete.json["message"]

    assert client.get(path).json == entry  # still there and unchanged


def test_owner_is_the_authenticated_user_not_the_body(
    client: FlaskClient, maya: tuple[str, str], stuart: tuple[str, str]
) -> None:
    mayas = make_entry(client, maya)
    stuarts = make_entry(client, stuart)
    assert mayas["owner_id"] != stuarts["owner_id"]
    assert client.patch(f"/roster/{stuarts['id']}", json={"level": 5}, auth=stuart).status_code == 200
    assert client.patch(f"/roster/{mayas['id']}", json={"level": 5}, auth=stuart).status_code == 403