from flask import Flask
from flask_cors import CORS
from flask_migrate import Migrate
from flask_apscheduler import APScheduler
from datetime import datetime, timezone, timedelta
from models import db, Announcement
from user_route import user
from superadmin_routes import superAdminBP
from middleware import auth_middleware
from socket_instance import socketio

app = Flask(__name__)

# App config
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
MYSQL_PASSWORD = '*****'  # Replace with a secure secret in production
MYSQL_HOST = 'localhost'
MYSQL_DB = 'test'

app.config['SQLALCHEMY_DATABASE_URI'] = f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}/{MYSQL_DB}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config.from_object(Config())

# Extensions initialization
db.init_app(app)
migrate = Migrate(app, db)
auth_middleware(app)
app.register_blueprint(user)
app.register_blueprint(superAdminBP)

scheduler = APScheduler()
scheduler.init_app(app)

def publish_scheduled_announcements():
    with app.app_context():
        ist = timezone(timedelta(hours=5, minutes=30))
        now = datetime.now(ist)
        print(f"[Scheduler] Checking for announcements at {now.isoformat()}")

        # Now filter using IST time
        announcements = Announcement.query.filter(
            Announcement.scheduled_time <= now,
            Announcement.is_published == False
        ).all()

        print(f"[Scheduler] Found {len(announcements)} announcements to publish")

        for a in announcements:
            print(f"  - Publishing: {a.title} (scheduled for {a.scheduled_time})")
            a.is_published = True

        if announcements:
            db.session.commit()
            print(f"[Scheduler] Published {len(announcements)} announcement(s)")
        else:
            print("[Scheduler] No announcements to publish.")


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