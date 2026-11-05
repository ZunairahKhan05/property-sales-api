from flask import Flask
from properties.properties import properties_bp
from auth.auth import auth_bp
from reviews.reviews import reviews_bp
from analytics.analytics import analytics_bp

app = Flask(__name__)

app.register_blueprint(properties_bp)
app.register_blueprint(auth_bp)
app.register_blueprint(reviews_bp)
app.register_blueprint(analytics_bp)

if __name__ == "__main__":
    app.run(debug=False, port=5001)