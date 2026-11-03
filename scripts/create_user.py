import os
import sys
from getpass import getpass

import bcrypt

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import globals

users = globals.db.users

username = input("Admin username: ").strip()
email = input("Admin email: ").strip().lower()
password = getpass("Admin password: ")

if len(password) < 8:
    print("Password must be at least 8 characters")
    sys.exit(1)

if users.find_one({"$or": [{"username": username}, {"email": email}]}) is not None:
    print("That username or email already exists")
    sys.exit(1)

users.insert_one({
    "username": username,
    "email": email,
    "password": bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()),
    "role": "admin",
    "watchlist": [],
    "saved_searches": [],
})
print("Admin created")