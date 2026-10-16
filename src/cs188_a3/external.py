from typing import Any
from urllib.parse import quote

import requests  # makes the HTTP calls to the external API

GENSHIN_API_BASE_URL = "https://genshin.jmp.blue"
CHARACTERS_PATH = "characters"
ELEMENTS_PATH = "elements"
REQUEST_TIMEOUT_SECONDS = 5  # never wait forever on a service we don't control
USER_AGENT = "cs188-a3-genshin-roster/0.1"


class EntityNotFound(Exception):
    """The external API has no entity with that slug."""


class ExternalServiceUnavailable(Exception):
    """The external API timed out, errored, or sent an unusable response."""


def _fetch_entity(entity_type: str, slug: str) -> dict[str, Any]:
    url = f"{GENSHIN_API_BASE_URL}/{entity_type}/{quote(slug, safe='')}"
    try:
        response = requests.get(
            url,
            params={"lang": "en"},
            headers={"User-Agent": USER_AGENT},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except requests.RequestException as err:
        raise ExternalServiceUnavailable(str(err)) from err
    if response.status_code == 404:
        raise EntityNotFound(slug)
    if not response.ok:
        raise ExternalServiceUnavailable(f"Unexpected status {response.status_code}")
    try:
        data = response.json()
    except ValueError as err:  # body was not valid JSON
        raise ExternalServiceUnavailable("Response was not JSON") from err
    if not isinstance(data, dict):
        raise ExternalServiceUnavailable("Response was not a JSON object")
    return data


def fetch_character(slug: str) -> dict[str, Any]:
    return _fetch_entity(CHARACTERS_PATH, slug)

def fetch_element(slug: str) -> dict[str, Any]:
    return _fetch_entity(ELEMENTS_PATH, slug)