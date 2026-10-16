import pytest
from cs188_a3 import external
from flask.testing import FlaskClient
from helpers import make_user

pytestmark = pytest.mark.live

def test_fetch_character_real_api() -> None:
    character = external.fetch_character("albedo")
    assert character["vision"] == "Geo"
    assert character["weapon"] == "Sword"
    assert character["rarity"] == 5


def test_fetch_element_real_api() -> None:
    element = external.fetch_element("pyro")
    assert element["name"] == "Pyro"
    assert any(reaction["name"] == "Vaporize" for reaction in element["reactions"])


def test_unknown_character_real_api() -> None:
    with pytest.raises(external.EntityNotFound):
        external.fetch_character("notarealperson")


def test_create_entry_through_app_with_real_api(live_client: FlaskClient) -> None:
    auth = make_user(live_client, "maya")
    response = live_client.post(
        "/roster",
        json={"character": "albedo", "level": 80, "constellation": 0, "role": "sub_dps"},
        auth=auth,
    )
    assert response.status_code == 201
    assert response.json["vision"] == "Geo"
    assert response.json["weapon_type"] == "Sword"


def test_unknown_character_through_app_with_real_api(live_client: FlaskClient) -> None:
    auth = make_user(live_client, "maya")
    response = live_client.post(
        "/roster",
        json={"character": "notarealperson", "level": 80, "constellation": 0,
              "role": "sub_dps"},
        auth=auth,
    )
    assert response.status_code == 400