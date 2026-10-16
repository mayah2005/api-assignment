from types import SimpleNamespace
from typing import Any

import pytest
import requests
from cs188_a3 import external


class FakeResponse:
    def __init__(
        self, status_code: int = 200, json_data: Any = None, bad_json: bool = False
    ) -> None:
        self.status_code = status_code
        self._json_data = json_data
        self._bad_json = bad_json

    @property
    def ok(self) -> bool:
        return self.status_code < 400

    def json(self) -> Any:
        if self._bad_json:
            raise ValueError("not json")
        return self._json_data


@pytest.fixture
def requests_get(monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    state = SimpleNamespace(response=FakeResponse(200, {"id": "x"}), error=None, calls=[])

    def fake_get(url: str, **kwargs: Any) -> FakeResponse:
        state.calls.append((url, kwargs))
        if state.error is not None:
            raise state.error
        return state.response

    monkeypatch.setattr(external.requests, "get", fake_get)
    return state


def test_fetch_character_returns_parsed_json(requests_get: SimpleNamespace) -> None:
    requests_get.response = FakeResponse(200, {"id": "albedo", "vision": "Geo"})
    assert external.fetch_character("albedo") == {"id": "albedo", "vision": "Geo"}


def test_fetch_character_builds_request(requests_get: SimpleNamespace) -> None:
    external.fetch_character("albedo")
    url, kwargs = requests_get.calls[0]
    assert url == f"{external.GENSHIN_API_BASE_URL}/characters/albedo"
    assert kwargs["params"] == {"lang": "en"}
    assert kwargs["headers"]["User-Agent"] == external.USER_AGENT
    assert kwargs["timeout"] == external.REQUEST_TIMEOUT_SECONDS > 0


def test_fetch_element_uses_elements_path(requests_get: SimpleNamespace) -> None:
    external.fetch_element("pyro")
    assert requests_get.calls[0][0] == f"{external.GENSHIN_API_BASE_URL}/elements/pyro"


def test_slug_is_url_encoded(requests_get: SimpleNamespace) -> None:
    external.fetch_character("a/b?c#d")
    url = requests_get.calls[0][0]
    assert url == f"{external.GENSHIN_API_BASE_URL}/characters/a%2Fb%3Fc%23d"


@pytest.mark.parametrize("fetch", [external.fetch_character, external.fetch_element])
def test_404_raises_entity_not_found(requests_get: SimpleNamespace, fetch: Any) -> None:
    requests_get.response = FakeResponse(404, {"error": "not found"})
    with pytest.raises(external.EntityNotFound):
        fetch("nobody")


@pytest.mark.parametrize("status", [400, 403, 429, 500, 502, 503])
def test_other_error_statuses_raise_unavailable(
    requests_get: SimpleNamespace, status: int
) -> None:
    requests_get.response = FakeResponse(status, {})
    with pytest.raises(external.ExternalServiceUnavailable):
        external.fetch_character("albedo")


@pytest.mark.parametrize(
    "error",
    [requests.Timeout("slow"), requests.ConnectionError("down"),
     requests.RequestException("other")],
)
def test_network_errors_raise_unavailable(
    requests_get: SimpleNamespace, error: Exception
) -> None:
    requests_get.error = error
    with pytest.raises(external.ExternalServiceUnavailable):
        external.fetch_character("albedo")


def test_invalid_json_raises_unavailable(requests_get: SimpleNamespace) -> None:
    requests_get.response = FakeResponse(200, bad_json=True)
    with pytest.raises(external.ExternalServiceUnavailable):
        external.fetch_character("albedo")


@pytest.mark.parametrize("payload", [[1, 2], "text", 5, None])
def test_non_object_json_raises_unavailable(
    requests_get: SimpleNamespace, payload: Any
) -> None:
    requests_get.response = FakeResponse(200, payload)
    with pytest.raises(external.ExternalServiceUnavailable):
        external.fetch_character("albedo")