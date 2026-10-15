import os
from functools import wraps
from pathlib import Path

from flask import Flask, g, request
from flask_bcrypt import Bcrypt
from flask_restful import Api, Resource, reqparse
from flask_talisman import Talisman

from cs188_a3._constants import PROJECT_ROOT
from cs188_a3.db import DEFAULT_DB_PATH, get_db

_KEYFILE_PATH = os.path.join(PROJECT_ROOT, "MyKey.pem")
_CERTIFICATE_PATH = os.path.join(PROJECT_ROOT, "MyCertificate.crt")

def main():
    run_app()

def auth_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        auth = request.authorization
        if auth is None:
            return {"message": "Authentication required"}, 401

        db = get_db()
        hashed_pwd = db.get_password(auth.username)
        valid = hashed_pwd is not None and Bcrypt().check_password_hash(
            hashed_pwd,
            auth.password,
        )
        if not valid:
            return {"message": "Invalid credentials"}, 401

        g.username = auth.username
        return func(*args, **kwargs)

    return wrapper

class Register(Resource):
    def put(self):
        parser = reqparse.RequestParser()
        parser.add_argument("username", type=str, required=True,
                            help="Username cannot be blank")
        parser.add_argument("password", type=str, required=True,
                            help="Password cannot be blank")
        args = parser.parse_args()
        username = args['username']
        password = args['password']
        # Hash the password before storing it
        hashed_pwd = Bcrypt().generate_password_hash(password).decode('utf-8')
        db = get_db()
        if db.add_user(username, hashed_pwd):
            return {"message": f"User {username} registered successfully"}
        return {"message": f"User {username} already exists"}, 409

class Profile(Resource):
    @auth_required
    def get(self):
        return {"message": f"Hello, {g.username}!"}

class Secret(Resource):
    @auth_required
    def get(self, num):
        return {"user": g.username, "cube": num ** 3}

def init_api(app):
    api = Api(app)
    api.add_resource(Register, "/register")
    api.add_resource(Profile, "/profile")
    api.add_resource(Secret, "/secret/<int:num>")
    return api

def create_app(db_path: str | Path = DEFAULT_DB_PATH) -> Flask:
    """Build and configure the Flask application."""
    app = Flask(__name__)
    app.config["PREFERRED_URL_SCHEME"] = "https"
    app.config["DB_PATH"] = str(db_path)
    Talisman(app, force_https=True)
    init_api(app)

    @app.teardown_appcontext
    def close_db(exc: BaseException | None) -> None:
        """Close the request's database connection, if one was opened."""
        db = g.pop("db", None)
        if db is not None:
            db.conn.close()

    return app

def run_app(debug: bool = True, with_ssl: bool = True) -> None:
    """Create the app and serve it, over HTTPS by default."""
    ssl_context = (_CERTIFICATE_PATH, _KEYFILE_PATH) if with_ssl else None
    create_app().run(debug=debug, ssl_context=ssl_context)