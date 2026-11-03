import os
from pymongo import MongoClient

SECRET_KEY = "com661-property-sales-api-secret-key-2026"

client = MongoClient("mongodb://localhost:27017")
db = client.propertyDB