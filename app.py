from flask import Flask
from properties.properties import properties_bp
from auth.auth import auth_bp

app = Flask(__name__)

app.register_blueprint(properties_bp)
app.register_blueprint(auth_bp)

if __name__ == "__main__":
    app.run(debug=True, port=5001)