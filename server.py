# server.py
from flask import Flask
from flask_cors import CORS
from flask_migrate import Migrate
from models import db
from user_route import user
from superadmin_routes import superAdminBP
from middleware import auth_middleware
from socket_instance import socketio  # ✅ Only import here

app = Flask(__name__)
CORS(app, supports_credentials=True,
     resources={r"/*": {"origins": [
         "http://localhost:5173",  # Vite frontend (development)
         "https://wzl6mwg3-5000.inc1.devtunnels.ms",  # DevTunnel public backend
     ]}},
     expose_headers=["Content-Type", "Authorization"],
     allow_headers=["Content-Type", "Authorization"])

MYSQL_USER = 'root'
MYSQL_PASSWORD = '*****'
MYSQL_HOST = 'localhost'
MYSQL_DB = 'test'

app.config['SQLALCHEMY_DATABASE_URI'] = f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}/{MYSQL_DB}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
migrate = Migrate(app, db)

with app.app_context():
    db.create_all()

auth_middleware(app)
app.register_blueprint(user)
app.register_blueprint(superAdminBP)

if __name__ == '__main__':
    socketio.init_app(app, cors_allowed_origins="*")
    socketio.run(app, debug=True, host="0.0.0.0", port=5000)
