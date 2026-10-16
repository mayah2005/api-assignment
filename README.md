# Genshin Roster API

A multi-user REST API for keeping track of your Genshin Impact characters. Registered users add characters to a personal roster (level, constellation, role, notes) and group them into teams of up to four. When a character is added, the API looks it up in the free [genshin.dev API](https://genshin.jmp.blue) to fill in its element, weapon type, and rarity, and a team's reactions endpoint uses the same service to list which elemental reactions its members can trigger.

**External API:** `https://genshin.jmp.blue` (no API key needed). This project uses two of its endpoints: `GET /characters/{slug}` and `GET /elements/{slug}`, both with an optional `lang` query parameter.

## Getting started

### Requirements

- Python 3.12 or newer
- [uv](https://docs.astral.sh/uv/)
- OpenSSL (to generate the HTTPS certificate)

### Install

```bash
uv sync
```

### HTTPS certificate

The server runs over HTTPS only. The certificate and key are never committed to Git. Generate a self-signed pair in the project root:

```bash
openssl req -x509 -newkey rsa:2048 -nodes -keyout MyKey.pem -out MyCertificate.crt -days 365 -subj "/CN=localhost"
```

### Run

```bash
uv run cs188-a3
```

The server listens on `https://127.0.0.1:5000`. Because the certificate is self-signed, use `curl -k` (or turn off SSL verification in Postman). Requests over plain `http://` are redirected or refused.

The SQLite database is created automatically as `cs188_a3.db` in the folder you run the server from.

### Test

```bash
uv run pytest                  # everything; the live tests need internet
uv run pytest -m "not live"    # offline only, skips the tests that call the real external API
```

Tests use a temporary database, and most of them replace the external API with an in-memory fake.

### Environment variables

None, the API does not need a key.

## Conventions

- Request and response bodies are JSON. Send `Content-Type: application/json` with a body.
- Every error response is JSON of the form `{"message": "..."}`, including 404s for URLs that don't exist.
- Endpoints that create, change, or delete records need HTTP Basic Auth (`-u username:password`). Reading never needs authentication.
- A request body that isn't a JSON object (for example a list, `null`, or invalid JSON) returns `400`.
- Ids in URLs must be positive integers. An id that doesn't exist, is zero, negative, non-numeric, or too large returns `404`.
- Only the owner of a record can change or delete it. Someone else gets `403`.
- Fields the server controls (`id`, `owner_id`, `created_at`, `vision`, `weapon_type`, `rarity`) cannot be set in a request body. Sending one returns `400`.

## Endpoint reference

| Method and path | Auth | Purpose |
|---|---|---|
| `POST /register` | no | Create a user account |
| `POST /roster` | yes | Add a character to your roster |
| `GET /roster` | no | List roster entries (filter and page) |
| `GET /roster/<id>` | no | Get one roster entry |
| `PATCH /roster/<id>` | yes (owner) | Update some fields of an entry |
| `DELETE /roster/<id>` | yes (owner) | Delete an entry |
| `POST /teams` | yes | Create a team from your roster entries |
| `GET /teams` | no | List teams |
| `GET /teams/<id>` | no | Get one team with its members |
| `DELETE /teams/<id>` | yes (owner) | Delete a team |
| `GET /teams/<id>/reactions` | no | Elemental reactions available within a team |

### POST /register

Creates an account.

| Body field | Type | Required | Description |
|---|---|---|---|
| `username` | string | yes | Non-blank, at most 50 characters. Must be unique. |
| `password` | string | yes | 8 to 72 characters. Stored only as a bcrypt hash. |

- **201:** `{"id": 1, "message": "User registered successfully"}`
- **400:** a field is missing, blank, the wrong type, or the wrong length, or the body isn't a JSON object.
- **409:** the username is already taken.

### Authentication errors (all protected endpoints)

- **401** `{"message": "Authentication required"}` when no credentials are sent.
- **401** `{"message": "Invalid username or password"}` for a wrong password or an unknown user. The message is identical so usernames can't be discovered.

### POST /roster

Creates a roster entry owned by the caller. Requires authentication. The server looks the character up in the external API and stores its element, weapon type, and rarity.

| Body field | Type | Required | Description |
|---|---|---|---|
| `character` | string | yes | Character slug such as `albedo` or `kamisato-ayaka`: lowercase letters, digits, and hyphens, up to 60 characters. Letters are lowercased. Must exist in the external API. |
| `level` | integer | yes | 1 to 90 |
| `constellation` | integer | yes | 0 to 6 |
| `role` | string | yes | One of `main_dps`, `sub_dps`, `support`, `healer` |
| `nickname` | string or null | no | Up to 40 characters, not blank |
| `notes` | string or null | no | Up to 500 characters, not blank |

- **201:** the new entry, with a `Location` header pointing to it.
- **400:** missing or invalid field, unrecognized field, or a character the external API doesn't know (`"Unknown character: ..."`).
- **401:** missing or bad credentials.
- **502:** the external API is down or returned something unusable. Nothing is stored.

Example response:

```json
{
  "id": 1,
  "owner_id": 1,
  "character": "albedo",
  "nickname": "Al",
  "level": 80,
  "constellation": 0,
  "role": "sub_dps",
  "notes": null,
  "vision": "Geo",
  "weapon_type": "Sword",
  "rarity": 5,
  "created_at": "2026-10-16T18:30:00.123456+00:00"
}
```

### GET /roster

Lists entries in id order. All query parameters are optional.

| Query parameter | Type | Description |
|---|---|---|
| `role` | string | Only entries with this role (one of the four roles) |
| `vision` | string | Only entries with this element, case-insensitive (for example `geo`) |
| `min_level` | integer, 1 to 90 | Only entries at or above this level |
| `limit` | integer, 1 to 100 | Maximum number of entries to return (default 20) |
| `offset` | integer, 0 or more | Number of entries to skip (default 0) |

- **200:** a JSON array of entries (empty if nothing matches).
- **400:** an invalid parameter value, with a message.

### GET /roster/\<id\>

- **200:** the entry.
- **404:** no entry with that id.

### PATCH /roster/\<id\>

Updates only the fields present in the body. Accepts the same fields and rules as `POST /roster`, but none are required, and at least one must be present. Changing `character` re-fetches the element, weapon type, and rarity. Send `null` for `nickname` or `notes` to clear them.

- **200:** the updated entry.
- **400:** invalid or unrecognized field, or an empty body.
- **401:** missing or bad credentials.
- **403:** the entry belongs to someone else.
- **404:** no entry with that id.
- **502:** the character was changed while the external API was down. Nothing is changed.

The checks run in the order 404, 403, then 400, so a non-owner never learns anything about validation.

### DELETE /roster/\<id\>

Deletes the entry and removes it from any teams.

- **204:** deleted, no body.
- **401**, **403**, **404:** as for PATCH.

### POST /teams

Creates a team owned by the caller. Requires authentication.

| Body field | Type | Required | Description |
|---|---|---|---|
| `name` | string | yes | Non-blank, at most 50 characters |
| `members` | array of integers | yes | 1 to 4 distinct ids of roster entries that **you** own |

- **201:** the new team with its members as full roster entries, and a `Location` header.
- **400:** invalid name or member list, an unrecognized field, or a roster id that doesn't exist.
- **401:** missing or bad credentials.
- **403:** one of the roster entries belongs to someone else. No team is created.

Example response:

```json
{
  "id": 1,
  "owner_id": 1,
  "name": "Geo Squad",
  "created_at": "2026-10-16T18:35:00.000000+00:00",
  "members": [ { "id": 1, "character": "albedo", "...": "full roster entry" } ]
}
```

### GET /teams

Lists teams in id order, each with its members. Supports `limit` (1 to 100, default 20) and `offset` (0 or more), as for `GET /roster`.

- **200:** a JSON array of teams.
- **400:** an invalid paging parameter.

### GET /teams/\<id\>

- **200:** the team with its members.
- **404:** no team with that id.

### DELETE /teams/\<id\>

Deletes the team. The roster entries on it are kept.

- **204:** deleted, no body.
- **401**, **403**, **404:** as for roster entries.

### GET /teams/\<id\>/reactions

Uses the external elements endpoint to find which elemental reactions are possible between the elements of a team's members. Only reactions between elements that are actually on the team are listed, and each pair is listed once.

- **200:**

  ```json
  {
    "team_id": 2,
    "elements": ["Hydro", "Pyro"],
    "reactions": [
      {"name": "Vaporize", "elements": ["Hydro", "Pyro"], "description": "When Pyro meets Hydro, ..."}
    ]
  }
  ```

- **404:** no team with that id.
- **502:** the external API is down or returned something unusable.

## Example session

These commands use `curl -k` for the self-signed certificate. On Windows PowerShell, type `curl.exe` instead of `curl`, and use Git Bash or WSL if the JSON quoting gives you trouble.

**1. Register two users**

```bash
curl -k -X POST https://127.0.0.1:5000/register \
  -H "Content-Type: application/json" \
  -d '{"username": "maya", "password": "cs188testcs188test"}'
# {"id": 1, "message": "User registered successfully"}

curl -k -X POST https://127.0.0.1:5000/register \
  -H "Content-Type: application/json" \
  -d '{"username": "stuart", "password": "cs188test"}'
# {"id": 2, "message": "User registered successfully"}
```

**2. Maya adds two characters**

```bash
curl -k -X POST https://127.0.0.1:5000/roster -u maya:cs188testcs188test \
  -H "Content-Type: application/json" \
  -d '{"character": "albedo", "level": 80, "constellation": 0, "role": "sub_dps", "nickname": "Al"}'
# 201, vision "Geo", weapon_type "Sword", rarity 5 filled in by the server

curl -k -X POST https://127.0.0.1:5000/roster -u maya:cs188testcs188test \
  -H "Content-Type: application/json" \
  -d '{"character": "xingqiu", "level": 70, "constellation": 2, "role": "support"}'
```

**3. List and filter (no authentication needed)**

```bash
curl -k "https://127.0.0.1:5000/roster?min_level=75"
# only albedo

curl -k "https://127.0.0.1:5000/roster?role=support&limit=5"
# only xingqiu
```

**4. Stuart tries to delete Maya's entry (fails)**

```bash
curl -k -i -X DELETE https://127.0.0.1:5000/roster/1 -u stuart:cs188test
# HTTP/1.1 403 FORBIDDEN
# {"message": "You do not own this roster entry"}
```

**5. Invalid input (fails)**

```bash
curl -k -X POST https://127.0.0.1:5000/roster -u maya:cs188test \
  -H "Content-Type: application/json" \
  -d '{"character": "albedo", "level": 500, "constellation": 0, "role": "sub_dps"}'
# 400 {"message": "level must be between 1 and 90"}
```

**6. Maya builds a team and checks its reactions**

```bash
curl -k -X POST https://127.0.0.1:5000/teams -u maya:cs188testcs188test \
  -H "Content-Type: application/json" \
  -d '{"name": "Geo Squad", "members": [1, 2]}'
# 201, team 1 with both members

curl -k https://127.0.0.1:5000/teams/1/reactions
# elements Geo and Hydro, with any reactions between them
```

## Project layout

```
src/cs188_a3/
  __init__.py     entry point exports
  app.py          create_app(), init_api(), run_app(): wiring only
  auth.py         the @auth_required decorator
  resources.py    Flask-RESTful resource classes (HTTP layer)
  services.py     the service layer: validation, ownership rules, business logic
  external.py     client for the genshin.dev API
  db.py           SQLite access and queries
  _constants.py   project-wide constants
tests/
  conftest.py, helpers.py   fixtures, fake external API, shared helpers
  test_auth.py, test_roster.py, test_teams.py
  test_services.py          service layer called directly, no Flask client
  test_external.py          the API client, with requests mocked
  test_live_external.py     the few tests that call the real API
```

## Git workflow

I forgot to create a separate branch for `user_authentication` so that was added retroactively.

## Resources and AI use

- **Documentation used:** the Flask, Flask-RESTful, Flask-Bcrypt, Flask-Talisman, `requests`, `sqlite3`, and pytest documentation; MDN's HTTP status code reference; and the genshin.dev API documentation at https://github.com/genshindev/api.
- **AI use:** I used AI as a tutor and code assistant throughout this project. It helped me built on the previous work from the in-class activity and answered questions regarding problems in my code that I could not find answers to elsewhere.
- **External API terms:** the genshin.dev API is free and keyless. The app sends a descriptive `User-Agent` header and uses a 5-second timeout.