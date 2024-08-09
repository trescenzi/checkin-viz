from flask import Response, request
from functools import wraps
from helpers import fetchone
from datetime import datetime


def last_modified(sql):
    """Executes sql which returns a value to compare against last_modified_at"""

    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            last_modified = fetchone(sql, []).last_modified
            if_modified_since = request.headers.get("If-Modified-Since")
            if if_modified_since and last_modified == datetime.fromisoformat(
                request.headers.get("If-Modified-Since")
            ):
                return Response(status=304)

            response = f(*args, **kwargs)
            if type(response) is str:
                response = Response(response)
            response.headers["Last-Modified"] = last_modified
            return response

        return decorated_function

    return decorator
