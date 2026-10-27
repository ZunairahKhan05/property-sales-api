import os
from pymongo import MongoClient

# Used to sign login tokens. Later we will set a real one outside the code.
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-secret")

# Connect to MongoDB running on your computer
client = MongoClient("mongodb://localhost:27017")
db = client.propertyDB