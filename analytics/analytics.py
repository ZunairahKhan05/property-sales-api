from flask import Blueprint, make_response, jsonify, request
from decorators import jwt_required
from properties.properties import VALID_TYPES
import globals

analytics_bp = Blueprint("analytics_bp", __name__)

properties = globals.db.properties


def read_filters():
    match = {}
    district = request.args.get("district")
    if district:
        match["address.district"] = district.upper()
    property_type = request.args.get("property_type")
    if property_type:
        if property_type not in VALID_TYPES:
            return None, "property_type must be one of " + ", ".join(VALID_TYPES)
        match["property_type"] = property_type
    return match, None


@analytics_bp.route("/api/v1.0/analytics/average-price", methods=["GET"])
@jwt_required
def average_price():
    match, error = read_filters()
    if error:
        return make_response(jsonify({"error": error}), 400)

    pipeline = [
        {"$match": match},
        {"$unwind": "$sales_history"},
        {"$group": {
            "_id": {"district": "$address.district", "property_type": "$property_type"},
            "average_price": {"$avg": "$sales_history.price"},
            "number_of_sales": {"$sum": 1},
        }},
        {"$project": {
            "_id": 0,
            "district": "$_id.district",
            "property_type": "$_id.property_type",
            "average_price": {"$toInt": {"$round": ["$average_price", 0]}},
            "number_of_sales": 1,
        }},
        {"$sort": {"average_price": -1, "district": 1}},
    ]
    return make_response(jsonify(list(properties.aggregate(pipeline))), 200)


@analytics_bp.route("/api/v1.0/analytics/price-trend", methods=["GET"])
@jwt_required
def price_trend():
    match, error = read_filters()
    if error:
        return make_response(jsonify({"error": error}), 400)

    pipeline = [
        {"$match": match},
        {"$unwind": "$sales_history"},
        {"$group": {
            "_id": {"$substrCP": ["$sales_history.date_of_transfer", 0, 7]},
            "average_price": {"$avg": "$sales_history.price"},
            "number_of_sales": {"$sum": 1},
        }},
        {"$sort": {"_id": 1}},
        {"$project": {
            "_id": 0,
            "month": "$_id",
            "average_price": {"$toInt": {"$round": ["$average_price", 0]}},
            "number_of_sales": 1,
        }},
    ]
    return make_response(jsonify(list(properties.aggregate(pipeline))), 200)