"""Application wiring: create_app, init_api, run_app."""
import os
from pathlib import Path

from flask import Flask, g
from flask_restful import Api
from flask_talisman import Talisman

from cs188_a3._constants import PROJECT_ROOT
from cs188_a3.db import DEFAULT_DB_PATH
from cs188_a3.resources import Register, RosterEntry, RosterList, TeamDetail, TeamList

_KEYFILE_PATH = os.path.join(PROJECT_ROOT, "MyKey.pem")
_CERTIFICATE_PATH = os.path.join(PROJECT_ROOT, "MyCertificate.crt")

def main() -> None:
    run_app()

def init_api(app: Flask) -> Api:
    api = Api(app, catch_all_404s=True)
    api.add_resource(Register, "/register")
    api.add_resource(RosterList, "/roster", endpoint="roster_list")
    api.add_resource(RosterEntry, "/roster/<int:entry_id>", endpoint="roster_entry")
    api.add_resource(TeamList, "/teams", endpoint="team_list")
    api.add_resource(TeamDetail, "/teams/<int:team_id>", endpoint="team_detail")
    return api

def create_app(db_path: str | Path = DEFAULT_DB_PATH) -> Flask:
    app = Flask(__name__)
    app.config["PREFERRED_URL_SCHEME"] = "https"
    app.config["DB_PATH"] = str(db_path)
    Talisman(app, force_https=True)
    init_api(app)

    @app.teardown_appcontext
    def close_db(exc: BaseException | None) -> None:
        db = g.pop("db", None)
        if db is not None:
            db.conn.close()
    return app

def run_app(debug: bool = True, with_ssl: bool = True) -> None:
    ssl_context = (_CERTIFICATE_PATH, _KEYFILE_PATH) if with_ssl else None
    create_app().run(debug=debug, ssl_context=ssl_context)