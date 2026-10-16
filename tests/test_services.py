import pytest

from cs188_a3 import services
from cs188_a3.db import Database
from helpers import PASSWORD, FakeGenshin

VALID_FIELDS = {"character": "albedo", "level": 80, "constellation": 0, "role": "sub_dps"}


@pytest.fixture
def owner_id(db: Database) -> int:
    return services.register_user(db, "owner", PASSWORD)


@pytest.fixture
def other_id(db: Database) -> int:
    return services.register_user(db, "other", PASSWORD)


def new_entry(db: Database, user_id: int, **overrides: object) -> dict:
    return services.create_entry(db, user_id, {**VALID_FIELDS, **overrides})



def test_register_user_returns_distinct_ids(db: Database) -> None:
    first = services.register_user(db, "first", PASSWORD)
    second = services.register_user(db, "second", PASSWORD)
    assert isinstance(first, int)
    assert first != second


def test_register_user_stores_hash_not_password(db: Database, owner_id: int) -> None:
    stored = db.get_user_credentials("owner")[1]
    assert stored != PASSWORD
    assert stored.startswith("$2")


def test_register_user_duplicate_raises(db: Database, owner_id: int) -> None:
    with pytest.raises(services.UsernameTaken):
        services.register_user(db, "owner", PASSWORD)


@pytest.mark.parametrize(
    ("username", "password"),
    [
        (None, PASSWORD), ("", PASSWORD), ("   ", PASSWORD), (123, PASSWORD),
        ("a" * 51, PASSWORD),
        ("maya", None), ("maya", ""), ("maya", "        "), ("maya", "short"),
        ("maya", "x" * 73), ("maya", 12345678),
    ],
)
def test_register_user_rejects_invalid_input(
    db: Database, username: object, password: object
) -> None:
    with pytest.raises(services.InvalidInput):
        services.register_user(db, username, password)


def test_authenticate_returns_user_id(db: Database, owner_id: int) -> None:
    assert services.authenticate(db, "owner", PASSWORD) == owner_id


@pytest.mark.usefixtures("owner_id")
@pytest.mark.parametrize(
    ("username", "password"), [("owner", "wrongpassword"), ("nobody", PASSWORD)]
)
def test_authenticate_rejects_bad_credentials(
    db: Database, username: str, password: str
) -> None:
    with pytest.raises(services.InvalidCredentials):
        services.authenticate(db, username, password)

def test_create_entry_fills_server_fields(db: Database, owner_id: int) -> None:
    entry = new_entry(db, owner_id, nickname="Al")
    assert entry["owner_id"] == owner_id
    assert isinstance(entry["id"], int)
    assert entry["created_at"]
    assert entry["nickname"] == "Al"
    assert (entry["vision"], entry["weapon_type"], entry["rarity"]) == ("Geo", "Sword", 5)


@pytest.mark.parametrize(
    ("field", "value"),
    [("id", 5), ("owner_id", 2), ("created_at", "2000-01-01"), ("vision", "Pyro")],
)
def test_create_entry_rejects_server_controlled_fields(
    db: Database, owner_id: int, field: str, value: object
) -> None:
    with pytest.raises(services.InvalidInput):
        new_entry(db, owner_id, **{field: value})


def test_create_entry_missing_required_field_raises(db: Database, owner_id: int) -> None:
    fields = {key: value for key, value in VALID_FIELDS.items() if key != "level"}
    with pytest.raises(services.InvalidInput):
        services.create_entry(db, owner_id, fields)


def test_create_entry_unknown_character_raises_invalid_input(
    db: Database, owner_id: int
) -> None:
    with pytest.raises(services.InvalidInput, match="notarealperson"):
        new_entry(db, owner_id, character="notarealperson")


def test_create_entry_external_outage_raises_and_stores_nothing(
    db: Database, owner_id: int, fake_genshin: FakeGenshin
) -> None:
    fake_genshin.down = True
    with pytest.raises(services.ServiceUnavailable):
        new_entry(db, owner_id)
    assert services.list_entries(db, {}) == []


@pytest.mark.parametrize("bad_id", [0, -1, 999, 2**63, 2**100])
def test_get_entry_missing_raises_not_found(db: Database, bad_id: int) -> None:
    with pytest.raises(services.NotFound):
        services.get_entry(db, bad_id)


@pytest.fixture
def three_entries(db: Database, owner_id: int) -> None:
    new_entry(db, owner_id, character="albedo", level=90, role="sub_dps")
    new_entry(db, owner_id, character="diluc", level=40, role="main_dps")
    new_entry(db, owner_id, character="xingqiu", level=70, role="support")


@pytest.mark.usefixtures("three_entries")
@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ({}, ["albedo", "diluc", "xingqiu"]),
        ({"role": "main_dps"}, ["diluc"]),
        ({"vision": "GEO"}, ["albedo"]),
        ({"min_level": "70"}, ["albedo", "xingqiu"]),
        ({"limit": "1", "offset": "1"}, ["diluc"]),
        ({"offset": "3"}, []),
    ],
)
def test_list_entries_filters_and_pages(
    db: Database, query: dict[str, str], expected: list[str]
) -> None:
    assert [e["character"] for e in services.list_entries(db, query)] == expected


@pytest.mark.parametrize(
    "query",
    [
        {"role": "tank"}, {"min_level": "abc"}, {"min_level": "0"}, {"limit": "0"},
        {"limit": "101"}, {"offset": "-1"}, {"offset": str(2**63)},
    ],
)
def test_list_entries_rejects_bad_queries(db: Database, query: dict[str, str]) -> None:
    with pytest.raises(services.InvalidInput):
        services.list_entries(db, query)


def test_update_entry_changes_only_given_fields(db: Database, owner_id: int) -> None:
    entry = new_entry(db, owner_id, nickname="Al")
    updated = services.update_entry(db, owner_id, entry["id"], {"level": 85})
    assert updated == {**entry, "level": 85}


def test_update_entry_missing_raises_not_found(db: Database, owner_id: int) -> None:
    with pytest.raises(services.NotFound):
        services.update_entry(db, owner_id, 999, {"level": 5})


def test_update_entry_by_non_owner_raises_forbidden(
    db: Database, owner_id: int, other_id: int
) -> None:
    entry = new_entry(db, owner_id)
    with pytest.raises(services.Forbidden):
        services.update_entry(db, other_id, entry["id"], {"level": 5})
    assert services.get_entry(db, entry["id"]) == entry


def test_update_entry_checks_ownership_before_validating(
    db: Database, owner_id: int, other_id: int
) -> None:
    entry = new_entry(db, owner_id)
    with pytest.raises(services.Forbidden):
        services.update_entry(db, other_id, entry["id"], {"level": 999})


def test_update_entry_empty_changes_raises(db: Database, owner_id: int) -> None:
    entry = new_entry(db, owner_id)
    with pytest.raises(services.InvalidInput):
        services.update_entry(db, owner_id, entry["id"], {})


def test_update_entry_character_change_refreshes_details(db: Database, owner_id: int) -> None:
    entry = new_entry(db, owner_id, character="albedo")
    updated = services.update_entry(db, owner_id, entry["id"], {"character": "diluc"})
    assert (updated["vision"], updated["weapon_type"]) == ("Pyro", "Claymore")

def test_delete_entry_removes_record(db: Database, owner_id: int) -> None:
    entry = new_entry(db, owner_id)
    services.delete_entry(db, owner_id, entry["id"])
    with pytest.raises(services.NotFound):
        services.get_entry(db, entry["id"])

def test_delete_entry_by_non_owner_raises_forbidden(
    db: Database, owner_id: int, other_id: int
) -> None:
    entry = new_entry(db, owner_id)
    with pytest.raises(services.Forbidden):
        services.delete_entry(db, other_id, entry["id"])
    assert services.get_entry(db, entry["id"]) == entry

def test_delete_entry_missing_raises_not_found(db: Database, owner_id: int) -> None:
    with pytest.raises(services.NotFound):
        services.delete_entry(db, owner_id, 999)

def new_team(db: Database, user_id: int, member_ids: list[int], name: str = "Team") -> dict:
    """Create a team through the service layer."""
    return services.create_team(db, user_id, {"name": name, "members": member_ids})

def test_create_team_includes_full_members(db: Database, owner_id: int) -> None:
    albedo = new_entry(db, owner_id, character="albedo")
    diluc = new_entry(db, owner_id, character="diluc")
    team = new_team(db, owner_id, [albedo["id"], diluc["id"]])
    assert team["owner_id"] == owner_id
    assert team["members"] == [albedo, diluc]

def test_create_team_with_someone_elses_entry_raises_forbidden(
    db: Database, owner_id: int, other_id: int
) -> None:
    theirs = new_entry(db, other_id)
    with pytest.raises(services.Forbidden):
        new_team(db, owner_id, [theirs["id"]])
    assert services.list_teams(db, {}) == []

def test_create_team_with_missing_member_raises_invalid_input(
    db: Database, owner_id: int
) -> None:
    with pytest.raises(services.InvalidInput, match="999"):
        new_team(db, owner_id, [999])

@pytest.mark.parametrize(
    "members", [[], [1, 1], [1, 2, 3, 4, 5], "1", None, [1.5], [True], [0], [-1], [2**63]]
)
def test_create_team_rejects_bad_member_lists(
    db: Database, owner_id: int, members: object
) -> None:
    new_entry(db, owner_id)
    with pytest.raises(services.InvalidInput):
        services.create_team(db, owner_id, {"name": "Team", "members": members})

@pytest.mark.parametrize("name", [None, "", "   ", 123, "x" * 51])
def test_create_team_rejects_bad_names(db: Database, owner_id: int, name: object) -> None:
    entry = new_entry(db, owner_id)
    with pytest.raises(services.InvalidInput):
        services.create_team(db, owner_id, {"name": name, "members": [entry["id"]]})

def test_get_team_missing_raises_not_found(db: Database) -> None:
    with pytest.raises(services.NotFound):
        services.get_team(db, 999)

def test_list_teams_pages_and_validates(db: Database, owner_id: int) -> None:
    entry = new_entry(db, owner_id)
    for number in range(3):
        new_team(db, owner_id, [entry["id"]], name=f"Team {number}")
    assert [t["name"] for t in services.list_teams(db, {"limit": "1", "offset": "1"})] == [
        "Team 1"]
    with pytest.raises(services.InvalidInput):
        services.list_teams(db, {"limit": "0"})

def test_delete_team_rules(db: Database, owner_id: int, other_id: int) -> None:
    entry = new_entry(db, owner_id)
    team = new_team(db, owner_id, [entry["id"]])
    with pytest.raises(services.Forbidden):
        services.delete_team(db, other_id, team["id"])
    services.delete_team(db, owner_id, team["id"])
    with pytest.raises(services.NotFound):
        services.get_team(db, team["id"])
    with pytest.raises(services.NotFound):
        services.delete_team(db, owner_id, team["id"])
    assert services.get_entry(db, entry["id"]) == entry

def test_deleting_entry_removes_it_from_team(db: Database, owner_id: int) -> None:
    albedo = new_entry(db, owner_id, character="albedo")
    diluc = new_entry(db, owner_id, character="diluc")
    team = new_team(db, owner_id, [albedo["id"], diluc["id"]])
    services.delete_entry(db, owner_id, albedo["id"])
    assert services.get_team(db, team["id"])["members"] == [diluc]

def test_team_reactions_finds_vaporize(db: Database, owner_id: int) -> None:
    pyro = new_entry(db, owner_id, character="diluc")
    hydro = new_entry(db, owner_id, character="xingqiu")
    team = new_team(db, owner_id, [pyro["id"], hydro["id"]])
    result = services.team_reactions(db, team["id"])
    assert result["elements"] == ["Hydro", "Pyro"]
    assert [r["name"] for r in result["reactions"]] == ["Vaporize"]

def test_team_reactions_missing_team_raises_not_found(db: Database) -> None:
    with pytest.raises(services.NotFound):
        services.team_reactions(db, 999)

def test_team_reactions_external_outage_raises(
    db: Database, owner_id: int, fake_genshin: FakeGenshin
) -> None:
    entry = new_entry(db, owner_id)
    team = new_team(db, owner_id, [entry["id"]])
    fake_genshin.down = True
    with pytest.raises(services.ServiceUnavailable):
        services.team_reactions(db, team["id"])