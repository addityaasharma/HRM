from flask import Flask, request, jsonify, g
import jwt, datetime
from functools import wraps

JWT_SECRET = 'thisismysecretkey'

# Token helpers
def create_tokens(user_id, role):
    access_payload = {
        'userID': user_id,
        'role': role,
        'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=5)
    }

    refresh_payload = {
        'userID': user_id,
        'role': role,
        'exp': datetime.datetime.utcnow() + datetime.timedelta(days=7)
    }

    access_token = jwt.encode(access_payload, JWT_SECRET, algorithm='HS256')
    refresh_token = jwt.encode(refresh_payload, JWT_SECRET, algorithm='HS256')

    return access_token, refresh_token


def decode_token(token):
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=['HS256'])
    except jwt.ExpiredSignatureError:
        return 'expired'
    except jwt.InvalidTokenError:
        return None


def auth_middleware(app):
    @app.before_request
    def _middleware():
        # ✅ Allow preflight CORS requests to pass through
        if request.method == "OPTIONS":
            return None

        exempt_paths = [
            '/superadmin/login',
            '/superadmin/signup',
            '/user/verify-signup',
            '/user/signup',
            '/user/login'
        ]

        if any(request.path.startswith(ep) for ep in exempt_paths):
            return None

        auth = request.headers.get("Authorization")
        if not auth or not auth.startswith("Bearer "):
            return jsonify({"message": "Token missing"}), 401

        token = auth.split(" ")[1]
        payload = decode_token(token)

        if payload == "expired":
            return jsonify({"message": "Token expired"}), 401
        elif payload is None:
            return jsonify({"message": "Invalid token"}), 401

        g.user = payload  # attach user data to flask.g

        return None


def require_role(*roles):
    def wrapper(func):
        @wraps(func)
        def decorator(*args, **kwargs):
            if not hasattr(g, 'user') or g.user.get("role") not in roles:
                return jsonify({"message": "Forbidden: Insufficient role"}), 403
            return func(*args, **kwargs)
        return decorator
    return wrapper
