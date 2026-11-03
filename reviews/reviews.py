import datetime
from flask import Blueprint, make_response, jsonify, request, g
from bson import ObjectId
from decorators import jwt_required
from properties.properties import to_object_id, whole_number
import globals

reviews_bp = Blueprint("reviews_bp", __name__)

properties = globals.db.properties


def clean_review(review):
    review["review_id"] = str(review["review_id"])
    return review


def read_review_form():
    rating = whole_number(request.form.get("rating"), 1, 5)
    if rating is None:
        return None, "rating must be a whole number from 1 to 5"
    comment = request.form.get("comment", "").strip()
    if len(comment) < 3 or len(comment) > 500:
        return None, "comment must be between 3 and 500 characters"
    return {"rating": rating, "comment": comment}, None


def find_review(object_id, review_object_id):
    prop = properties.find_one(
        {"_id": object_id, "reviews.review_id": review_object_id},
        {"reviews.$": 1}
    )
    if prop is None:
        return None
    return prop["reviews"][0]


@reviews_bp.route("/api/v1.0/properties/<string:property_id>/reviews", methods=["GET"])
def show_reviews(property_id):
    object_id = to_object_id(property_id)
    if object_id is None:
        return make_response(jsonify({"error": "Invalid property ID"}), 400)

    prop = properties.find_one({"_id": object_id}, {"reviews": 1})
    if prop is None:
        return make_response(jsonify({"error": "Property not found"}), 404)

    return make_response(jsonify([clean_review(review) for review in prop.get("reviews", [])]), 200)


@reviews_bp.route("/api/v1.0/properties/<string:property_id>/reviews/<string:review_id>", methods=["GET"])
def show_one_review(property_id, review_id):
    object_id = to_object_id(property_id)
    review_object_id = to_object_id(review_id)
    if object_id is None or review_object_id is None:
        return make_response(jsonify({"error": "Invalid property or review ID"}), 400)

    review = find_review(object_id, review_object_id)
    if review is None:
        return make_response(jsonify({"error": "Property or review not found"}), 404)

    return make_response(jsonify(clean_review(review)), 200)


@reviews_bp.route("/api/v1.0/properties/<string:property_id>/reviews", methods=["POST"])
@jwt_required
def add_review(property_id):
    object_id = to_object_id(property_id)
    if object_id is None:
        return make_response(jsonify({"error": "Invalid property ID"}), 400)

    fields, error = read_review_form()
    if error:
        return make_response(jsonify({"error": error}), 400)

    prop = properties.find_one({"_id": object_id}, {"reviews.user": 1})
    if prop is None:
        return make_response(jsonify({"error": "Property not found"}), 404)

    if any(review["user"] == g.user["user"] for review in prop.get("reviews", [])):
        return make_response(jsonify({"error": "You have already reviewed this property"}), 409)

    review = {
        "review_id": ObjectId(),
        "user": g.user["user"],
        "rating": fields["rating"],
        "comment": fields["comment"],
        "date": datetime.date.today().isoformat(),
    }
    properties.update_one({"_id": object_id}, {"$push": {"reviews": review}})

    link = request.url_root + "api/v1.0/properties/" + property_id + "/reviews/" + str(review["review_id"])
    return make_response(jsonify({"url": link}), 201)


@reviews_bp.route("/api/v1.0/properties/<string:property_id>/reviews/<string:review_id>", methods=["PUT"])
@jwt_required
def edit_review(property_id, review_id):
    object_id = to_object_id(property_id)
    review_object_id = to_object_id(review_id)
    if object_id is None or review_object_id is None:
        return make_response(jsonify({"error": "Invalid property or review ID"}), 400)

    review = find_review(object_id, review_object_id)
    if review is None:
        return make_response(jsonify({"error": "Property or review not found"}), 404)

    if review["user"] != g.user["user"] and g.user["role"] != "admin":
        return make_response(jsonify({"error": "You can only change your own reviews"}), 403)

    fields, error = read_review_form()
    if error:
        return make_response(jsonify({"error": error}), 400)

    properties.update_one(
        {"_id": object_id, "reviews.review_id": review_object_id},
        {"$set": {
            "reviews.$.rating": fields["rating"],
            "reviews.$.comment": fields["comment"],
            "reviews.$.edited": datetime.date.today().isoformat(),
        }}
    )
    return make_response(jsonify({"message": "Review updated"}), 200)


@reviews_bp.route("/api/v1.0/properties/<string:property_id>/reviews/<string:review_id>", methods=["DELETE"])
@jwt_required
def delete_review(property_id, review_id):
    object_id = to_object_id(property_id)
    review_object_id = to_object_id(review_id)
    if object_id is None or review_object_id is None:
        return make_response(jsonify({"error": "Invalid property or review ID"}), 400)

    review = find_review(object_id, review_object_id)
    if review is None:
        return make_response(jsonify({"error": "Property or review not found"}), 404)

    if review["user"] != g.user["user"] and g.user["role"] != "admin":
        return make_response(jsonify({"error": "You can only delete your own reviews"}), 403)

    properties.update_one({"_id": object_id}, {"$pull": {"reviews": {"review_id": review_object_id}}})
    return make_response(jsonify({"message": "Review deleted"}), 200)