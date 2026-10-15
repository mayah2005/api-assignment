from typing import Any

# quote() keeps odd characters in the slug from changing the URL's path
from urllib.parse import quote

import requests  # makes the HTTP calls to the external API

GENSHIN_API_BASE_URL = "https://genshin.jmp.blue"
REQUEST_TIMEOUT_SECONDS = 5
USER_AGENT = "cs188-a3-genshin-roster/0.1"

class CharacterNotFound(Exception):
    """The external API has no character with that slug."""

class ExternalServiceUnavailable(Exception):
    """The external API timed out, errored, or sent an unusable response."""

def fetch_character(slug: str) -> dict[str, Any]:
    url = f"{GENSHIN_API_BASE_URL}/characters/{quote(slug, safe='')}"
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
        raise CharacterNotFound(slug)
    if not response.ok:
        raise ExternalServiceUnavailable(f"Unexpected status {response.status_code}")
    try:
        data = response.json()
    except ValueError as err:
        raise ExternalServiceUnavailable("Response was not JSON") from err
    if not isinstance(data, dict):
        raise ExternalServiceUnavailable("Response was not a JSON object")
    return data