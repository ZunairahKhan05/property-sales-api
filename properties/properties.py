from flask import Blueprint, make_response, jsonify
import globals

properties_bp = Blueprint("properties_bp", __name__)

properties = globals.db.properties


@properties_bp.route("/api/v1.0/properties", methods=["GET"])
def show_all_properties():
    total = properties.count_documents({})
    return make_response(jsonify({"message": "Properties API is running", "count": total}), 200)