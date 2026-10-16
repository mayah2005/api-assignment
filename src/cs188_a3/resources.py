from typing import Any

from flask import g, request, url_for
from flask_restful import Resource

from cs188_a3 import services
from cs188_a3.auth import auth_required
from cs188_a3.db import get_db


def parse_json_object() -> dict[str, Any]:
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        raise services.InvalidInput("Request body must be a JSON object")
    return body

class Register(Resource):
    def post(self) -> tuple[dict[str, Any], int]:
        try:
            body = parse_json_object()
            user_id = services.register_user(
                get_db(), body.get("username"), body.get("password")
            )
        except services.InvalidInput as err:
            return {"message": str(err)}, 400
        except services.UsernameTaken:
            return {"message": "Username already taken"}, 409
        return {"id": user_id, "message": "User registered successfully"}, 201


class RosterList(Resource):
    def get(self) -> tuple[Any, int]:
        try:
            entries = services.list_entries(get_db(), request.args)
        except services.InvalidInput as err:
            return {"message": str(err)}, 400
        return entries, 200

    @auth_required
    def post(self) -> tuple[Any, int, dict[str, str]]:
        try:
            entry = services.create_entry(get_db(), g.user_id, parse_json_object())
        except services.InvalidInput as err:
            return {"message": str(err)}, 400
        except services.ServiceUnavailable as err:
            return {"message": str(err)}, 502
        location = url_for("roster_entry", entry_id=entry["id"], _external=True)
        return entry, 201, {"Location": location}

class RosterEntry(Resource):
    def get(self, entry_id: int) -> tuple[Any, int]:
        try:
            return services.get_entry(get_db(), entry_id), 200
        except services.NotFound:
            return {"message": "Roster entry not found"}, 404

    @auth_required
    def patch(self, entry_id: int) -> tuple[Any, int]:
        try:
            entry = services.update_entry(
                get_db(), g.user_id, entry_id, parse_json_object()
            )
        except services.NotFound:
            return {"message": "Roster entry not found"}, 404
        except services.Forbidden:
            return {"message": "You do not own this roster entry"}, 403
        except services.InvalidInput as err:
            return {"message": str(err)}, 400
        except services.ServiceUnavailable as err:
            return {"message": str(err)}, 502
        return entry, 200

    @auth_required
    def delete(self, entry_id: int) -> tuple[Any, int]:
        try:
            services.delete_entry(get_db(), g.user_id, entry_id)
        except services.NotFound:
            return {"message": "Roster entry not found"}, 404
        except services.Forbidden:
            return {"message": "You do not own this roster entry"}, 403
        return "", 204

class TeamList(Resource):
    def get(self) -> tuple[Any, int]:
        try:
            return services.list_teams(get_db(), request.args), 200
        except services.InvalidInput as err:
            return {"message": str(err)}, 400

    @auth_required
    def post(self) -> tuple[Any, int, dict[str, str]]:
        try:
            team = services.create_team(get_db(), g.user_id, parse_json_object())
        except services.InvalidInput as err:
            return {"message": str(err)}, 400
        except services.Forbidden:
            return {"message": "You can only add your own roster entries"}, 403
        location = url_for("team_detail", team_id=team["id"], _external=True)
        return team, 201, {"Location": location}

class TeamDetail(Resource):
    def get(self, team_id: int) -> tuple[Any, int]:
        try:
            return services.get_team(get_db(), team_id), 200
        except services.NotFound:
            return {"message": "Team not found"}, 404

    @auth_required
    def delete(self, team_id: int) -> tuple[Any, int]:
        try:
            services.delete_team(get_db(), g.user_id, team_id)
        except services.NotFound:
            return {"message": "Team not found"}, 404
        except services.Forbidden:
            return {"message": "You do not own this team"}, 403
        return "", 204

class TeamReactions(Resource):
    def get(self, team_id: int) -> tuple[Any, int]:
        try:
            return services.team_reactions(get_db(), team_id), 200
        except services.NotFound:
            return {"message": "Team not found"}, 404
        except services.ServiceUnavailable as err:
            return {"message": str(err)}, 502