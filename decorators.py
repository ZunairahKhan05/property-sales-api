from functools import wraps
from flask import request, make_response, jsonify, g
import jwt
import globals

blacklist = globals.db.blacklist


def get_token_data():
    token = request.headers.get("x-access-token")
    if not token:
        return None, "Token is missing"
    try:
        data = jwt.decode(token, globals.SECRET_KEY, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        return None, "Token has expired"
    except jwt.InvalidTokenError:
        return None, "Token is invalid"
    if blacklist.find_one({"token": token}) is not None:
        return None, "Token has been cancelled"
    return data, None


def jwt_required(func):
    @wraps(func)
    def jwt_required_wrapper(*args, **kwargs):
        data, error = get_token_data()
        if error:
            return make_response(jsonify({"error": error}), 401)
        g.user = data
        return func(*args, **kwargs)
    return jwt_required_wrapper


def admin_required(func):
    @wraps(func)
    def admin_required_wrapper(*args, **kwargs):
        if g.user.get("role") != "admin":
            return make_response(jsonify({"error": "Admin access required"}), 403)
        return func(*args, **kwargs)
    return admin_required_wrapper