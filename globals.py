import os
from pymongo import MongoClient

SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-secret")

client = MongoClient("mongodb://localhost:27017")
db = client.propertyDB