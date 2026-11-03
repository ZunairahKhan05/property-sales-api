import re
import datetime
import bcrypt
import jwt
from flask import Blueprint, make_response, jsonify, request, g
from decorators import jwt_required
import globals

auth_bp = Blueprint("auth_bp", __name__)

users = globals.db.users
blacklist = globals.db.blacklist

blacklist.create_index("expires_at", expireAfterSeconds=0)

USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_]{3,30}$")
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@auth_bp.route("/api/v1.0/auth/register", methods=["POST"])
def register():
    username = request.form.get("username", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    if not USERNAME_PATTERN.match(username):
        return make_response(jsonify({"error": "Username must be 3 to 30 characters: letters, numbers and underscores"}), 400)
    if not EMAIL_PATTERN.match(email):
        return make_response(jsonify({"error": "A valid email address is required"}), 400)
    if len(password) < 8:
        return make_response(jsonify({"error": "Password must be at least 8 characters"}), 400)

    if users.find_one({"$or": [{"username": username}, {"email": email}]}) is not None:
        return make_response(jsonify({"error": "Username or email already in use"}), 409)

    users.insert_one({
        "username": username,
        "email": email,
        "password": bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()),
        "role": "user",
        "watchlist": [],
        "saved_searches": [],
    })
    return make_response(jsonify({"message": "Account created"}), 201)


@auth_bp.route("/api/v1.0/auth/login", methods=["GET"])
def login():
    auth = request.authorization
    if auth is None or not auth.username or not auth.password:
        return make_response(jsonify({"error": "Username and password are required using Basic Auth"}), 401,
                             {"WWW-Authenticate": 'Basic realm="Login required"'})

    user = users.find_one({"username": auth.username.strip()})
    if user is None or not bcrypt.checkpw(auth.password.encode("utf-8"), user["password"]):
        return make_response(jsonify({"error": "Invalid username or password"}), 401)

    token = jwt.encode({
        "user": user["username"],
        "role": user["role"],
        "exp": datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=8),
    }, globals.SECRET_KEY, algorithm="HS256")

    return make_response(jsonify({"token": token, "role": user["role"]}), 200)


@auth_bp.route("/api/v1.0/auth/logout", methods=["GET"])
@jwt_required
def logout():
    token = request.headers["x-access-token"]
    expires_at = datetime.datetime.fromtimestamp(g.user["exp"], datetime.timezone.utc)
    blacklist.insert_one({"token": token, "expires_at": expires_at})
    return make_response(jsonify({"message": "Logout successful"}), 200)


@auth_bp.route("/api/v1.0/auth/me", methods=["GET"])
@jwt_required
def me():
    return make_response(jsonify({"username": g.user["user"], "role": g.user["role"]}), 200)