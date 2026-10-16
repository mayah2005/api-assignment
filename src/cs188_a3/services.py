import re
from typing import Any, Mapping

from flask_bcrypt import Bcrypt  # hashes and verifies passwords

from cs188_a3 import external
from cs188_a3.db import Database

MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 72
MAX_USERNAME_LENGTH = 50

ROLES = ("main_dps", "sub_dps", "support", "healer")
MIN_LEVEL, MAX_LEVEL = 1, 90
MIN_CONSTELLATION, MAX_CONSTELLATION = 0, 6
MAX_NICKNAME_LENGTH = 40
MAX_NOTES_LENGTH = 500
MAX_CHARACTER_LENGTH = 60
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100
MAX_SQLITE_INT = 2**63 - 1  # larger integers make sqlite3 raise OverflowError
CHARACTER_SLUG_PATTERN = re.compile(r"[a-z0-9-]+")
EDITABLE_FIELDS = {"character", "nickname", "level", "constellation", "role", "notes"}
REQUIRED_FIELDS = {"character", "level", "constellation", "role"}
MAX_TEAM_SIZE = 4
MAX_TEAM_NAME_LENGTH = 50

_bcrypt = Bcrypt()

class ServiceError(Exception):
    """Base class for errors the service layer raises."""

class InvalidInput(ServiceError):
    """The caller supplied data that fails validation."""

class UsernameTaken(ServiceError):
    """A user with that username already exists."""

class InvalidCredentials(ServiceError):
    """The username or password is wrong."""

class NotFound(ServiceError):
    """The requested record does not exist."""

class Forbidden(ServiceError):
    """The caller does not own the record."""

class ServiceUnavailable(ServiceError):
    """A service this app depends on is down or misbehaving."""

def register_user(db: Database, username: object, password: object) -> int:
    if not isinstance(username, str) or not username.strip():
        raise InvalidInput("Username must be a non-blank string")
    if len(username) > MAX_USERNAME_LENGTH:
        raise InvalidInput(f"Username must be at most {MAX_USERNAME_LENGTH} characters")
    if not isinstance(password, str) or not password.strip():
        raise InvalidInput("Password must be a non-blank string")
    if not MIN_PASSWORD_LENGTH <= len(password) <= MAX_PASSWORD_LENGTH:
        raise InvalidInput(
            f"Password must be {MIN_PASSWORD_LENGTH}-{MAX_PASSWORD_LENGTH} characters"
        )
    hashed = _bcrypt.generate_password_hash(password).decode("utf-8")
    user_id = db.add_user(username, hashed)
    if user_id is None:
        raise UsernameTaken(username)
    return user_id

def authenticate(db: Database, username: str, password: str) -> int:
    creds = db.get_user_credentials(username)
    if creds is None or not _bcrypt.check_password_hash(creds[1], password):
        raise InvalidCredentials()
    return creds[0]

def _clean_int(value: object, name: str, minimum: int, maximum: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise InvalidInput(f"{name} must be an integer")
    if not minimum <= value <= maximum:
        raise InvalidInput(f"{name} must be between {minimum} and {maximum}")
    return value

def _clean_text(value: object, name: str, max_length: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise InvalidInput(f"{name} must be a non-blank string")
    if len(value) > max_length:
        raise InvalidInput(f"{name} must be at most {max_length} characters")
    return value.strip()

def _clean_optional_text(value: object, name: str, max_length: int) -> str | None:
    return None if value is None else _clean_text(value, name, max_length)

def _clean_character(value: object) -> str:
    slug = _clean_text(value, "character", MAX_CHARACTER_LENGTH).lower()
    if not CHARACTER_SLUG_PATTERN.fullmatch(slug):
        raise InvalidInput("character must be a slug like 'kamisato-ayaka'")
    return slug

def _clean_fields(fields: Mapping[str, Any], *, partial: bool) -> dict[str, Any]:
    unknown = set(fields) - EDITABLE_FIELDS
    if unknown:
        raise InvalidInput(f"Unrecognized field(s): {', '.join(sorted(unknown))}")
    missing = REQUIRED_FIELDS - set(fields)
    if missing and not partial:
        raise InvalidInput(f"Missing required field(s): {', '.join(sorted(missing))}")
    cleaned: dict[str, Any] = {}
    if "character" in fields:
        cleaned["character"] = _clean_character(fields["character"])
    if "nickname" in fields:
        cleaned["nickname"] = _clean_optional_text(
            fields["nickname"], "nickname", MAX_NICKNAME_LENGTH)
    if "level" in fields:
        cleaned["level"] = _clean_int(fields["level"], "level", MIN_LEVEL, MAX_LEVEL)
    if "constellation" in fields:
        cleaned["constellation"] = _clean_int(
            fields["constellation"], "constellation",
            MIN_CONSTELLATION, MAX_CONSTELLATION)
    if "role" in fields:
        if fields["role"] not in ROLES:  # also rejects non-strings like lists
            raise InvalidInput(f"role must be one of: {', '.join(ROLES)}")
        cleaned["role"] = fields["role"]
    if "notes" in fields:
        cleaned["notes"] = _clean_optional_text(
            fields["notes"], "notes", MAX_NOTES_LENGTH)
    return cleaned

def _character_details(slug: str) -> dict[str, Any]:
    try:
        data = external.fetch_character(slug)
    except external.EntityNotFound:
        raise InvalidInput(f"Unknown character: {slug}") from None
    except external.ExternalServiceUnavailable as err:
        raise ServiceUnavailable("Character data service is unavailable") from err
    return {
        "vision": data.get("vision"),
        "weapon_type": data.get("weapon"),
        "rarity": data.get("rarity"),
    }

def create_entry(db: Database, user_id: int, fields: Mapping[str, Any]) -> dict[str, Any]:
    cleaned = _clean_fields(fields, partial=False)
    cleaned.setdefault("nickname", None)
    cleaned.setdefault("notes", None)
    cleaned.update(_character_details(cleaned["character"]))
    return get_entry(db, db.add_entry(user_id, cleaned))

def get_entry(db: Database, entry_id: int) -> dict[str, Any]:
    entry = db.get_entry(entry_id) if 0 < entry_id <= MAX_SQLITE_INT else None
    if entry is None:
        raise NotFound()
    return entry

def _parse_query_int(
    query: Mapping[str, str], name: str, default: int | None, minimum: int, maximum: int
) -> int | None:
    raw = query.get(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        raise InvalidInput(f"{name} must be an integer") from None
    if not minimum <= value <= maximum:
        raise InvalidInput(f"{name} must be between {minimum} and {maximum}")
    return value

def list_entries(db: Database, query: Mapping[str, str]) -> list[dict[str, Any]]:
    role = query.get("role")
    if role is not None and role not in ROLES:
        raise InvalidInput(f"role must be one of: {', '.join(ROLES)}")
    vision = query.get("vision")
    min_level = _parse_query_int(query, "min_level", None, MIN_LEVEL, MAX_LEVEL)
    limit = _parse_query_int(query, "limit", DEFAULT_PAGE_SIZE, 1, MAX_PAGE_SIZE)
    offset = _parse_query_int(query, "offset", 0, 0, MAX_SQLITE_INT)
    return db.list_entries(
        role, vision.lower() if vision else None, min_level, limit, offset)

def update_entry(
    db: Database, user_id: int, entry_id: int, changes: Mapping[str, Any]
) -> dict[str, Any]:
    entry = get_entry(db, entry_id)  # 404 first, then 403, then validation
    if entry["owner_id"] != user_id:
        raise Forbidden()
    cleaned = _clean_fields(changes, partial=True)
    if not cleaned:
        raise InvalidInput("No fields to update")
    if "character" in cleaned and cleaned["character"] != entry["character"]:
        cleaned.update(_character_details(cleaned["character"]))  # refresh stored details
    db.update_entry(entry_id, {**entry, **cleaned})
    return get_entry(db, entry_id)

def delete_entry(db: Database, user_id: int, entry_id: int) -> None:
    entry = get_entry(db, entry_id)
    if entry["owner_id"] != user_id:
        raise Forbidden()
    db.delete_entry(entry_id)

def _clean_member_ids(value: object) -> list[int]:
    if not isinstance(value, list) or not 1 <= len(value) <= MAX_TEAM_SIZE:
        raise InvalidInput(
            f"members must be a list of 1-{MAX_TEAM_SIZE} roster entry ids")
    ids = [_clean_int(item, "member id", 1, MAX_SQLITE_INT) for item in value]
    if len(set(ids)) != len(ids):
        raise InvalidInput("members must not contain duplicates")
    return ids

def _team_view(db: Database, team: dict[str, Any]) -> dict[str, Any]:
    member_ids = team.pop("member_ids")
    return {**team, "members": [db.get_entry(member_id) for member_id in member_ids]}

def create_team(db: Database, user_id: int, fields: Mapping[str, Any]) -> dict[str, Any]:
    unknown = set(fields) - {"name", "members"}
    if unknown:
        raise InvalidInput(f"Unrecognized field(s): {', '.join(sorted(unknown))}")
    name = _clean_text(fields.get("name"), "name", MAX_TEAM_NAME_LENGTH)
    member_ids = _clean_member_ids(fields.get("members"))
    for member_id in member_ids:
        entry = db.get_entry(member_id)
        if entry is None:
            raise InvalidInput(f"Roster entry {member_id} does not exist")
        if entry["owner_id"] != user_id:  # you can only team up your own characters
            raise Forbidden()
    return get_team(db, db.add_team(user_id, name, member_ids))

def get_team(db: Database, team_id: int) -> dict[str, Any]:
    team = db.get_team(team_id) if 0 < team_id <= MAX_SQLITE_INT else None
    if team is None:
        raise NotFound()
    return _team_view(db, team)

def list_teams(db: Database, query: Mapping[str, str]) -> list[dict[str, Any]]:
    limit = _parse_query_int(query, "limit", DEFAULT_PAGE_SIZE, 1, MAX_PAGE_SIZE)
    offset = _parse_query_int(query, "offset", 0, 0, MAX_SQLITE_INT)
    return [_team_view(db, team) for team in db.list_teams(limit, offset)]

def delete_team(db: Database, user_id: int, team_id: int) -> None:
    team = db.get_team(team_id) if 0 < team_id <= MAX_SQLITE_INT else None
    if team is None:
        raise NotFound()
    if team["owner_id"] != user_id:
        raise Forbidden()
    db.delete_team(team_id)

def team_reactions(db: Database, team_id: int) -> dict[str, Any]:
    team = get_team(db, team_id)
    elements = sorted({m["vision"].lower() for m in team["members"] if m["vision"]})
    found: dict[tuple[str, tuple[str, ...]], dict[str, Any]] = {}
    for slug in elements:
        try:
            element = external.fetch_element(slug)
        except external.EntityNotFound:
            continue  # no data for this element, so it contributes no reactions
        except external.ExternalServiceUnavailable as err:
            raise ServiceUnavailable("Element data service is unavailable") from err
        own_name = element.get("name", slug.title())
        for reaction in element.get("reactions", []):
            for partner in reaction.get("elements", []):
                if partner.lower() not in elements:
                    continue  # that partner element isn't on this team
                pair = tuple(sorted([own_name, partner]))
                # Keyed by (reaction, pair) so it isn't listed once per element
                found[(reaction["name"], pair)] = {
                    "name": reaction["name"],
                    "elements": list(pair),
                    "description": reaction.get("description"),
                }
    return {
        "team_id": team_id,
        "elements": [slug.title() for slug in elements],
        "reactions": sorted(found.values(), key=lambda item: item["name"]),
    }