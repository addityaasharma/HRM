from flask import Flask
from flask_cors import CORS
from flask_migrate import Migrate
from models import db, Announcement
from user_route import user
from superadmin_routes import superAdminBP
from middleware import auth_middleware
from socket_instance import socketio
from flask_apscheduler import APScheduler
from datetime import datetime

app = Flask(__name__)

class Config:
    SCHEDULER_API_ENABLED = True

# CORS setup
CORS(app, supports_credentials=True,
     resources={r"/*": {"origins": [
         "http://localhost:5173",
         "https://wzl6mwg3-5000.inc1.devtunnels.ms",
     ]}},
     expose_headers=["Content-Type", "Authorization"],
     allow_headers=["Content-Type", "Authorization"])

# Database config
MYSQL_USER = 'root'
MYSQL_PASSWORD = '*****'  # Keep this secret in production!
MYSQL_HOST = 'localhost'
MYSQL_DB = 'test'

app.config['SQLALCHEMY_DATABASE_URI'] = f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}/{MYSQL_DB}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config.from_object(Config())

db.init_app(app)
migrate = Migrate(app, db)

auth_middleware(app)
app.register_blueprint(user)
app.register_blueprint(superAdminBP)

scheduler = APScheduler()
scheduler.init_app(app)

def publish_scheduled_announcements():
    with app.app_context():
        now = datetime.utcnow()
        announcements = Announcement.query.filter(
            Announcement.scheduled_time <= now,
            Announcement.is_published == False
        ).all()

        for announcement in announcements:
            announcement.is_published = True

        if announcements:
            db.session.commit()
            print(f"{len(announcements)} announcement(s) published at {now}.")

with app.app_context():
    db.create_all()

if __name__ == '__main__':
    scheduler.add_job(
        id='publish_announcements',
        func=publish_scheduled_announcements,
        trigger='interval',
        seconds=60
    )
    scheduler.start()

    socketio.init_app(app, cors_allowed_origins="*")
    socketio.run(app, debug=True, host="0.0.0.0", port=5000)
