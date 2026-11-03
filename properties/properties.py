import re
import uuid
import datetime
from flask import Blueprint, make_response, jsonify, request
from bson import ObjectId
from bson.errors import InvalidId
from decorators import jwt_required, admin_required
import globals

properties_bp = Blueprint("properties_bp", __name__)

properties = globals.db.properties

VALID_TYPES = ["detached", "semi-detached", "terraced", "flat", "other"]
VALID_TENURES = ["freehold", "leasehold"]
POSTCODE_PATTERN = re.compile(r"^[A-Z]{1,2}[0-9][A-Z0-9]? ?[0-9][A-Z]{2}$")


def clean(prop):
    prop["_id"] = str(prop["_id"])
    for sale in prop.get("sales_history", []):
        sale["sale_id"] = str(sale["sale_id"])
    for review in prop.get("reviews", []):
        if "review_id" in review:
            review["review_id"] = str(review["review_id"])
    return prop


def to_object_id(value):
    try:
        return ObjectId(value)
    except InvalidId:
        return None


def whole_number(value, low, high):
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    if number < low or number > high:
        return None
    return number


def read_property_form():
    form = request.form
    required = ["paon", "street", "town", "district", "postcode",
                "property_type", "tenure", "bedrooms", "bathrooms", "floor_area_sqm"]
    missing = [name for name in required if not form.get(name, "").strip()]
    if missing:
        return None, "Missing form data: " + ", ".join(missing)

    postcode = form["postcode"].strip().upper()
    if not POSTCODE_PATTERN.match(postcode):
        return None, "postcode is not a valid UK postcode"
    if form["property_type"] not in VALID_TYPES:
        return None, "property_type must be one of " + ", ".join(VALID_TYPES)
    if form["tenure"] not in VALID_TENURES:
        return None, "tenure must be freehold or leasehold"

    bedrooms = whole_number(form["bedrooms"], 0, 20)
    if bedrooms is None:
        return None, "bedrooms must be a whole number from 0 to 20"
    bathrooms = whole_number(form["bathrooms"], 0, 20)
    if bathrooms is None:
        return None, "bathrooms must be a whole number from 0 to 20"
    floor_area = whole_number(form["floor_area_sqm"], 5, 2000)
    if floor_area is None:
        return None, "floor_area_sqm must be a whole number from 5 to 2000"

    features = [item.strip() for item in form.get("features", "").split(",") if item.strip()]

    fields = {
        "address": {
            "paon": form["paon"].strip().upper(),
            "saon": form.get("saon", "").strip().upper(),
            "street": form["street"].strip().upper(),
            "locality": form.get("locality", "").strip().upper(),
            "town": form["town"].strip().upper(),
            "district": form["district"].strip().upper(),
            "county": "GREATER LONDON",
            "postcode": postcode,
        },
        "property_type": form["property_type"],
        "tenure": form["tenure"],
        "details": {
            "bedrooms": bedrooms,
            "bathrooms": bathrooms,
            "floor_area_sqm": floor_area,
            "features": features,
            "synthetic": False,
        },
    }
    return fields, None


def address_exists(address, exclude_id=None):
    query = {
        "address.postcode": address["postcode"],
        "address.paon": address["paon"],
        "address.saon": address["saon"],
        "address.street": address["street"],
    }
    if exclude_id is not None:
        query["_id"] = {"$ne": exclude_id}
    return properties.find_one(query) is not None


def read_sale_form():
    form = request.form
    price = whole_number(form.get("price"), 1, 100000000)
    if price is None:
        return None, "price must be a whole number between 1 and 100000000"

    try:
        sale_date = datetime.datetime.strptime(form.get("date_of_transfer", ""), "%Y-%m-%d").date()
    except ValueError:
        return None, "date_of_transfer must be a real date in the form YYYY-MM-DD"
    if sale_date > datetime.date.today():
        return None, "date_of_transfer cannot be in the future"

    new_build = form.get("new_build", "N").upper()
    if new_build not in ["Y", "N"]:
        return None, "new_build must be Y or N"

    return {
        "price": price,
        "date_of_transfer": sale_date.isoformat(),
        "new_build": new_build == "Y",
    }, None


@properties_bp.route("/api/v1.0/properties", methods=["GET"])
def show_all_properties():
    try:
        page_num = int(request.args.get("pn", 1))
        page_size = int(request.args.get("ps", 10))
        min_price = request.args.get("min_price")
        max_price = request.args.get("max_price")
        min_price = int(min_price) if min_price else None
        max_price = int(max_price) if max_price else None
        bedrooms = request.args.get("bedrooms")
        bedrooms = int(bedrooms) if bedrooms else None
    except ValueError:
        return make_response(jsonify({"error": "pn, ps, min_price, max_price and bedrooms must be whole numbers"}), 400)

    if page_num < 1 or page_size < 1 or page_size > 100:
        return make_response(jsonify({"error": "pn must be 1 or more and ps must be between 1 and 100"}), 400)

    if min_price is not None and max_price is not None and min_price > max_price:
        return make_response(jsonify({"error": "min_price cannot be greater than max_price"}), 400)

    query = {}

    district = request.args.get("district")
    if district:
        query["address.district"] = district.upper()

    postcode = request.args.get("postcode")
    if postcode:
        query["address.postcode"] = {"$regex": "^" + re.escape(postcode.upper())}

    property_type = request.args.get("property_type")
    if property_type:
        if property_type not in VALID_TYPES:
            return make_response(jsonify({"error": "property_type must be one of " + ", ".join(VALID_TYPES)}), 400)
        query["property_type"] = property_type

    tenure = request.args.get("tenure")
    if tenure:
        if tenure not in VALID_TENURES:
            return make_response(jsonify({"error": "tenure must be freehold or leasehold"}), 400)
        query["tenure"] = tenure

    if bedrooms is not None:
        query["details.bedrooms"] = bedrooms

    sort_options = {
        "price_asc": ("latest_sale.price", 1),
        "price_desc": ("latest_sale.price", -1),
        "newest": ("latest_sale.date_of_transfer", -1),
        "oldest": ("latest_sale.date_of_transfer", 1),
    }
    sort_key = request.args.get("sort")
    if sort_key and sort_key not in sort_options:
        return make_response(jsonify({"error": "sort must be one of " + ", ".join(sort_options)}), 400)

    pipeline = [
        {"$match": query},
        {"$addFields": {"latest_sale": {"$last": {"$sortArray": {
            "input": "$sales_history",
            "sortBy": {"date_of_transfer": 1},
        }}}}},
        {"$unset": ["latest_sale.sale_id", "latest_sale.transaction_id"]},
    ]

    price_filter = {}
    if min_price is not None:
        price_filter["$gte"] = min_price
    if max_price is not None:
        price_filter["$lte"] = max_price
    if price_filter:
        pipeline.append({"$match": {"latest_sale.price": price_filter}})

    count_result = list(properties.aggregate(pipeline + [{"$count": "total"}]))
    total = count_result[0]["total"] if count_result else 0

    if sort_key:
        field, direction = sort_options[sort_key]
        sort_stage = {"$sort": {field: direction, "_id": 1}}
    else:
        sort_stage = {"$sort": {"_id": 1}}

    page_start = page_size * (page_num - 1)
    pipeline += [sort_stage, {"$skip": page_start}, {"$limit": page_size}]

    results = [clean(prop) for prop in properties.aggregate(pipeline)]

    return make_response(jsonify({
        "page": page_num,
        "page_size": page_size,
        "total": total,
        "results": results,
    }), 200)


@properties_bp.route("/api/v1.0/properties/<string:property_id>", methods=["GET"])
def show_one_property(property_id):
    object_id = to_object_id(property_id)
    if object_id is None:
        return make_response(jsonify({"error": "Invalid property ID"}), 400)

    prop = properties.find_one({"_id": object_id})
    if prop is None:
        return make_response(jsonify({"error": "Property not found"}), 404)

    return make_response(jsonify(clean(prop)), 200)


@properties_bp.route("/api/v1.0/properties", methods=["POST"])
@jwt_required
@admin_required
def add_property():
    fields, error = read_property_form()
    if error:
        return make_response(jsonify({"error": error}), 400)

    if address_exists(fields["address"]):
        return make_response(jsonify({"error": "A property with this address already exists"}), 409)

    fields["sales_history"] = []
    fields["reviews"] = []
    fields["viewings"] = []

    new_id = properties.insert_one(fields).inserted_id
    link = request.url_root + "api/v1.0/properties/" + str(new_id)
    return make_response(jsonify({"url": link}), 201)


@properties_bp.route("/api/v1.0/properties/<string:property_id>", methods=["PUT"])
@jwt_required
@admin_required
def edit_property(property_id):
    object_id = to_object_id(property_id)
    if object_id is None:
        return make_response(jsonify({"error": "Invalid property ID"}), 400)

    fields, error = read_property_form()
    if error:
        return make_response(jsonify({"error": error}), 400)

    if address_exists(fields["address"], object_id):
        return make_response(jsonify({"error": "Another property already has this address"}), 409)

    result = properties.update_one({"_id": object_id}, {"$set": fields})
    if result.matched_count == 0:
        return make_response(jsonify({"error": "Property not found"}), 404)

    link = request.url_root + "api/v1.0/properties/" + property_id
    return make_response(jsonify({"url": link}), 200)


@properties_bp.route("/api/v1.0/properties/<string:property_id>", methods=["DELETE"])
@jwt_required
@admin_required
def delete_property(property_id):
    object_id = to_object_id(property_id)
    if object_id is None:
        return make_response(jsonify({"error": "Invalid property ID"}), 400)

    result = properties.delete_one({"_id": object_id})
    if result.deleted_count == 0:
        return make_response(jsonify({"error": "Property not found"}), 404)

    return make_response(jsonify({"message": "Property deleted"}), 200)


@properties_bp.route("/api/v1.0/properties/<string:property_id>/sales", methods=["GET"])
def show_sales(property_id):
    object_id = to_object_id(property_id)
    if object_id is None:
        return make_response(jsonify({"error": "Invalid property ID"}), 400)

    prop = properties.find_one({"_id": object_id}, {"sales_history": 1})
    if prop is None:
        return make_response(jsonify({"error": "Property not found"}), 404)

    return make_response(jsonify(clean(prop)["sales_history"]), 200)


@properties_bp.route("/api/v1.0/properties/<string:property_id>/sales", methods=["POST"])
@jwt_required
@admin_required
def add_sale(property_id):
    object_id = to_object_id(property_id)
    if object_id is None:
        return make_response(jsonify({"error": "Invalid property ID"}), 400)

    sale, error = read_sale_form()
    if error:
        return make_response(jsonify({"error": error}), 400)

    sale["sale_id"] = ObjectId()
    sale["transaction_id"] = str(uuid.uuid4()).upper()

    result = properties.update_one({"_id": object_id}, {"$push": {"sales_history": sale}})
    if result.matched_count == 0:
        return make_response(jsonify({"error": "Property not found"}), 404)

    return make_response(jsonify({"sale_id": str(sale["sale_id"])}), 201)


@properties_bp.route("/api/v1.0/properties/<string:property_id>/sales/<string:sale_id>", methods=["PUT"])
@jwt_required
@admin_required
def edit_sale(property_id, sale_id):
    object_id = to_object_id(property_id)
    sale_object_id = to_object_id(sale_id)
    if object_id is None or sale_object_id is None:
        return make_response(jsonify({"error": "Invalid property or sale ID"}), 400)

    sale, error = read_sale_form()
    if error:
        return make_response(jsonify({"error": error}), 400)

    result = properties.update_one(
        {"_id": object_id, "sales_history.sale_id": sale_object_id},
        {"$set": {
            "sales_history.$.price": sale["price"],
            "sales_history.$.date_of_transfer": sale["date_of_transfer"],
            "sales_history.$.new_build": sale["new_build"],
        }}
    )
    if result.matched_count == 0:
        return make_response(jsonify({"error": "Property or sale not found"}), 404)

    return make_response(jsonify({"message": "Sale updated"}), 200)


@properties_bp.route("/api/v1.0/properties/<string:property_id>/sales/<string:sale_id>", methods=["DELETE"])
@jwt_required
@admin_required
def delete_sale(property_id, sale_id):
    object_id = to_object_id(property_id)
    sale_object_id = to_object_id(sale_id)
    if object_id is None or sale_object_id is None:
        return make_response(jsonify({"error": "Invalid property or sale ID"}), 400)

    result = properties.update_one(
        {"_id": object_id},
        {"$pull": {"sales_history": {"sale_id": sale_object_id}}}
    )
    if result.matched_count == 0:
        return make_response(jsonify({"error": "Property not found"}), 404)
    if result.modified_count == 0:
        return make_response(jsonify({"error": "Sale not found"}), 404)

    return make_response(jsonify({"message": "Sale deleted"}), 200)