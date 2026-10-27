import pandas as pd

columns = [
    "transaction_id", "price", "date_of_transfer", "postcode",
    "property_type", "new_build", "tenure", "paon", "saon",
    "street", "locality", "town", "district", "county",
    "ppd_category", "record_status",
]

df = pd.read_csv("data/pp-2026.csv", header=None, names=columns,
                 dtype=str, keep_default_na=False)
print("Total rows:", len(df))

london = df[df["county"] == "GREATER LONDON"]
print("London rows:", len(london))
london.to_csv("data/london_2026.csv", index=False)