import pytest
from flask.testing import FlaskClient
from helpers import (
    BAD_IDS,
    FAKE_CHARACTERS,
    NOT_JSON_OBJECTS,
    FakeGenshin,
    make_entry,
    make_team,
)


def test_create_team_happy_path(client: FlaskClient, maya: tuple[str, str]) -> None:
    albedo = make_entry(client, maya, character="albedo")
    diluc = make_entry(client, maya, character="diluc")
    response = client.post(
        "/teams", json={"name": "Geo Squad", "members": [albedo["id"], diluc["id"]]},
        auth=maya)
    assert response.status_code == 201
    team = response.json
    assert team["name"] == "Geo Squad"
    assert team["members"] == [albedo, diluc]
    assert team["owner_id"] == albedo["owner_id"]
    assert team["created_at"]
    assert response.headers["Location"].endswith(f"/teams/{team['id']}")
    assert client.get(f"/teams/{team['id']}").json == team

def test_create_team_with_maximum_members(client: FlaskClient, maya: tuple[str, str]) -> None:
    ids = [make_entry(client, maya)["id"] for _ in range(4)]
    assert client.post("/teams", json={"name": "Full", "members": ids},
                       auth=maya).status_code == 201


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"members": [1]},
        {"name": "Team"},
        {"name": "", "members": [1]},
        {"name": "   ", "members": [1]},
        {"name": 123, "members": [1]},
        {"name": None, "members": [1]},
        {"name": "x" * 51, "members": [1]},
        {"name": "Team", "members": []},
        {"name": "Team", "members": [1, 1]},
        {"name": "Team", "members": [1, 2, 3, 4, 5]},
        {"name": "Team", "members": "1"},
        {"name": "Team", "members": None},
        {"name": "Team", "members": [1.5]},
        {"name": "Team", "members": ["1"]},
        {"name": "Team", "members": [True]},
        {"name": "Team", "members": [0]},
        {"name": "Team", "members": [-1]},
        {"name": "Team", "members": [2**63]},
        {"name": "Team", "members": [1], "id": 5},
        {"name": "Team", "members": [1], "owner_id": 2},
        {"name": "Team", "members": [1], "created_at": "2000-01-01"},
    ],
)

def test_create_team_rejects_invalid_body(
    client: FlaskClient, maya: tuple[str, str], body: dict
) -> None:
    make_entry(client, maya)  # roster entry 1 exists, so id 1 is valid where used
    response = client.post("/teams", json=body, auth=maya)
    assert response.status_code == 400
    assert response.json["message"]
    assert client.get("/teams").json == []

@pytest.mark.parametrize(("data", "content_type"), NOT_JSON_OBJECTS)
def test_create_team_rejects_non_object_body(
    client: FlaskClient, maya: tuple[str, str], data: str, content_type: str
) -> None:
    response = client.post("/teams", data=data, content_type=content_type, auth=maya)
    assert response.status_code == 400
    assert response.json["message"]


def test_create_team_with_nonexistent_member_returns_400(
    client: FlaskClient, maya: tuple[str, str]
) -> None:
    response = client.post("/teams", json={"name": "Ghost", "members": [999]}, auth=maya)
    assert response.status_code == 400
    assert "999" in response.json["message"]


def test_create_team_with_someone_elses_entry_returns_403(
    client: FlaskClient, maya: tuple[str, str], stuart: tuple[str, str]
) -> None:
    mine = make_entry(client, maya)
    theirs = make_entry(client, stuart)
    response = client.post(
        "/teams", json={"name": "Steal", "members": [mine["id"], theirs["id"]]}, auth=maya)
    assert response.status_code == 403
    assert response.json["message"]
    assert client.get("/teams").json == []

def test_list_teams_empty(client: FlaskClient) -> None:
    response = client.get("/teams")
    assert response.status_code == 200
    assert response.json == []

def test_list_teams_paging(client: FlaskClient, maya: tuple[str, str]) -> None:
    entry = make_entry(client, maya)
    for number in range(1, 4):
        make_team(client, maya, [entry["id"]], name=f"Team {number}")

    def names(query: str) -> list[str]:
        return [team["name"] for team in client.get(f"/teams?{query}").json]

    assert names("") == ["Team 1", "Team 2", "Team 3"]
    assert names("limit=2") == ["Team 1", "Team 2"]
    assert names("limit=1&offset=1") == ["Team 2"]
    assert names("offset=3") == []


@pytest.mark.parametrize(
    "query", ["limit=0", "limit=101", "limit=abc", "offset=-1", "offset=abc"]
)
def test_list_teams_rejects_bad_query_parameters(client: FlaskClient, query: str) -> None:
    response = client.get(f"/teams?{query}")
    assert response.status_code == 400
    assert response.json["message"]

@pytest.mark.parametrize("bad_id", BAD_IDS)
def test_get_team_nonexistent_or_malformed_id_returns_404(
    client: FlaskClient, bad_id: str
) -> None:
    response = client.get(f"/teams/{bad_id}")
    assert response.status_code == 404
    assert response.json["message"]

def test_reading_teams_does_not_call_external_api(
    client: FlaskClient, maya: tuple[str, str], fake_genshin: FakeGenshin
) -> None:
    entry = make_entry(client, maya)
    team = make_team(client, maya, [entry["id"]])
    fake_genshin.calls.clear()
    fake_genshin.down = True
    assert client.get("/teams").status_code == 200
    assert client.get(f"/teams/{team['id']}").status_code == 200
    assert fake_genshin.calls == []

def test_delete_team_keeps_roster_entries(client: FlaskClient, maya: tuple[str, str]) -> None:
    entry = make_entry(client, maya)
    team = make_team(client, maya, [entry["id"]])
    assert client.delete(f"/teams/{team['id']}", auth=maya).status_code == 204
    assert client.get(f"/teams/{team['id']}").status_code == 404
    assert client.delete(f"/teams/{team['id']}", auth=maya).status_code == 404
    assert client.get(f"/roster/{entry['id']}").status_code == 200

def test_other_user_can_read_but_not_delete_team(
    client: FlaskClient, maya: tuple[str, str], stuart: tuple[str, str]
) -> None:
    entry = make_entry(client, maya)
    team = make_team(client, maya, [entry["id"]])
    path = f"/teams/{team['id']}"
    assert client.get(path, auth=stuart).json == team
    response = client.delete(path, auth=stuart)
    assert response.status_code == 403
    assert response.json["message"]
    assert client.get(path).json == team


@pytest.mark.parametrize("bad_id", BAD_IDS)
def test_delete_team_nonexistent_or_malformed_id_returns_404(
    client: FlaskClient, maya: tuple[str, str], bad_id: str
) -> None:
    assert client.delete(f"/teams/{bad_id}", auth=maya).status_code == 404

def test_deleting_roster_entry_removes_it_from_teams(
    client: FlaskClient, maya: tuple[str, str]
) -> None:
    albedo = make_entry(client, maya, character="albedo")
    diluc = make_entry(client, maya, character="diluc")
    team = make_team(client, maya, [albedo["id"], diluc["id"]])
    assert client.delete(f"/roster/{albedo['id']}", auth=maya).status_code == 204
    members = client.get(f"/teams/{team['id']}").json["members"]
    assert members == [diluc]

def _reactions(client: FlaskClient, maya: tuple[str, str], characters: list[str]) -> dict:
    ids = [make_entry(client, maya, character=name)["id"] for name in characters]
    team = make_team(client, maya, ids)
    response = client.get(f"/teams/{team['id']}/reactions")
    assert response.status_code == 200
    assert response.json["team_id"] == team["id"]
    return response.json

def test_reactions_between_two_elements(client: FlaskClient, maya: tuple[str, str]) -> None:
    result = _reactions(client, maya, ["diluc", "xingqiu"])
    assert result["elements"] == ["Hydro", "Pyro"]
    assert [(r["name"], r["elements"]) for r in result["reactions"]] == [
        ("Vaporize", ["Hydro", "Pyro"])]

def test_reactions_only_include_elements_on_the_team(
    client: FlaskClient, maya: tuple[str, str]
) -> None:
    names = [r["name"] for r in _reactions(client, maya, ["diluc", "xingqiu"])["reactions"]]
    assert "Overloaded" not in names

def test_reactions_with_three_elements(client: FlaskClient, maya: tuple[str, str]) -> None:
    result = _reactions(client, maya, ["albedo", "diluc", "xingqiu"])
    assert result["elements"] == ["Geo", "Hydro", "Pyro"]
    assert [r["name"] for r in result["reactions"]] == [
        "Crystallize", "Crystallize", "Vaporize"]

def test_reactions_for_single_element_team_is_empty(
    client: FlaskClient, maya: tuple[str, str]
) -> None:
    result = _reactions(client, maya, ["albedo"])
    assert result["elements"] == ["Geo"]
    assert result["reactions"] == []

def test_reactions_list_each_element_once(client: FlaskClient, maya: tuple[str, str]) -> None:
    assert _reactions(client, maya, ["albedo", "albedo"])["elements"] == ["Geo"]

def test_reactions_skip_elements_the_external_api_does_not_know(
    client: FlaskClient, maya: tuple[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(
        FAKE_CHARACTERS, "venti", {"vision": "Anemo", "weapon": "Bow", "rarity": 5})
    result = _reactions(client, maya, ["venti", "diluc"])
    assert result["elements"] == ["Anemo", "Pyro"]
    assert result["reactions"] == []

@pytest.mark.parametrize("bad_id", BAD_IDS)
def test_reactions_nonexistent_or_malformed_team_returns_404(
    client: FlaskClient, bad_id: str
) -> None:
    response = client.get(f"/teams/{bad_id}/reactions")
    assert response.status_code == 404
    assert response.json["message"]

def test_reactions_return_502_when_external_api_is_down(
    client: FlaskClient, maya: tuple[str, str], fake_genshin: FakeGenshin
) -> None:
    entry = make_entry(client, maya)
    team = make_team(client, maya, [entry["id"]])
    fake_genshin.down = True
    response = client.get(f"/teams/{team['id']}/reactions")
    assert response.status_code == 502
    assert response.json["message"]