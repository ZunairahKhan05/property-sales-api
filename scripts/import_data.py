import os
import sys
import random

import pandas as pd
from bson import ObjectId

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import globals

random.seed(42)

TYPES = {"D": "detached", "S": "semi-detached", "T": "terraced",
         "F": "flat", "O": "other"}
TENURES = {"F": "freehold", "L": "leasehold"}
FEATURES = ["garden", "parking", "balcony", "garage",
            "central heating", "double glazing", "lift", "fireplace"]
BEDROOM_RANGES = {"flat": (1, 3), "terraced": (2, 4), "semi-detached": (2, 4),
                  "detached": (3, 5), "other": (1, 4)}


def make_details(property_type):
    low, high = BEDROOM_RANGES[property_type]
    bedrooms = random.randint(low, high)
    return {
        "bedrooms": bedrooms,
        "bathrooms": random.randint(1, 1 + bedrooms // 2),
        "floor_area_sqm": bedrooms * random.randint(20, 30) + random.randint(15, 30),
        "features": random.sample(FEATURES, random.randint(1, 4)),
        "synthetic": True,
    }


df = pd.read_csv("data/london_2026.csv", dtype=str, keep_default_na=False)
print("Sales read:", len(df))

df["key"] = df["postcode"] + "|" + df["paon"] + "|" + df["saon"] + "|" + df["street"]

properties = []
for key, group in df.groupby("key"):
    group = group.sort_values("date_of_transfer")
    first = group.iloc[0]
    property_type = TYPES.get(first["property_type"], "other")

    sales_history = []
    for _, row in group.iterrows():
        sales_history.append({
            "sale_id": ObjectId(),
            "transaction_id": row["transaction_id"],
            "price": int(row["price"]),
            "date_of_transfer": row["date_of_transfer"][:10],
            "new_build": row["new_build"] == "Y",
        })

    properties.append({
        "address": {
            "paon": first["paon"],
            "saon": first["saon"],
            "street": first["street"],
            "locality": first["locality"],
            "town": first["town"],
            "district": first["district"],
            "county": first["county"],
            "postcode": first["postcode"],
        },
        "property_type": property_type,
        "tenure": TENURES.get(first["tenure"], "unknown"),
        "sales_history": sales_history,
        "details": make_details(property_type),
        "reviews": [],
        "viewings": [],
    })

collection = globals.db.properties
collection.drop()
collection.insert_many(properties)
print("Properties inserted:", collection.count_documents({}))