from functools import wraps
from typing import Any, Callable

from flask import g, request

from cs188_a3 import services
from cs188_a3.db import get_db


def auth_required(func: Callable[..., Any]) -> Callable[..., Any]:
    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        auth = request.authorization
        if auth is None or auth.username is None or auth.password is None:
            return {"message": "Authentication required"}, 401
        try:
            g.user_id = services.authenticate(get_db(), auth.username, auth.password)
        except services.InvalidCredentials:
            return {"message": "Invalid username or password"}, 401
        return func(*args, **kwargs)

    return wrapper