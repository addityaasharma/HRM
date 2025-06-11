from models import db
from flask import Flask
from user_route import user
from superadmin_routes import superAdminBP
from middleware import auth_middleware
from flask_migrate import Migrate
from flask_cors import CORS

app = Flask(__name__)
CORS(app, supports_credentials=True, 
     resources={r"/*": {"origins": "*"}},  # <-- your Vite/Vue port
     expose_headers=["Content-Type", "Authorization"],
     allow_headers=["Content-Type", "Authorization"])

MYSQL_USER = 'root'
MYSQL_PASSWORD = '*****'
MYSQL_HOST = 'localhost'
MYSQL_DB = 'test'


app.config['SQLALCHEMY_DATABASE_URI'] = (
    f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}"
    f"@{MYSQL_HOST}/{MYSQL_DB}"
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
migrate = Migrate(app,db)

with app.app_context():
    db.create_all()


auth_middleware(app)

# user blueprints    
app.register_blueprint(user)
app.register_blueprint(superAdminBP)


if __name__ == '__main__':
    app.run(debug=True, host="0.0.0.0", port=5000)
