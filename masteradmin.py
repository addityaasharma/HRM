from werkzeug.security import generate_password_hash, check_password_hash
from flask import Blueprint, request, jsonify, g
from models import db, Master, MasterPanel
from middleware import create_tokens  # Assuming you have a JWT token creation utility
from flask import Blueprint


masterBP = Blueprint('masteradmin',__name__, url_prefix='/master')

@masterBP.route('/signup', methods=['POST'])
def master_signup():
    data = request.get_json()
    required_fields = ['company_email', 'company_password']

    if not data or not all(field in data for field in required_fields):
        return jsonify({"status": "error", "message": "All fields are required"}), 400

    if Master.query.filter_by(company_email=data['company_email']).first():
        return jsonify({"status": "error", "message": "Master admin already exists"}), 400

    hashed_password = generate_password_hash(data['company_password'])

    new_master = Master(
        name=data['name'],
        company_email=data['company_email'],
        company_password=hashed_password
    )

    db.session.add(new_master)
    db.session.flush()

    new_master.masteradminPanel = MasterPanel(masterid=new_master.id)

    db.session.commit()

    access_token, refresh_token = create_tokens(user_id=new_master.id, role='master_admin')

    return jsonify({
        "status": "success",
        "message": "Master admin registered successfully",
        "data": {
            "id": new_master.id,
            "name": new_master.name,
            "email": new_master.company_email,
            "panel_id": new_master.masteradminPanel.id
        },
        "token": {
            "access_token": access_token,
            "refresh_token": refresh_token
        }
    }), 201


@masterBP.route('/login', methods=['POST'])
def master_login():
    data = request.get_json()
    required_fields = ['company_email', 'company_password']

    if not data or not all(field in data for field in required_fields):
        return jsonify({"status": "error", "message": "All fields are required"}), 400

    master = Master.query.filter_by(company_email=data['company_email']).first()

    if not master or not check_password_hash(master.company_password, data['company_password']):
        return jsonify({"status": "error", "message": "Invalid email or password"}), 401

    access_token, refresh_token = create_tokens(user_id=master.id, role='master_admin')

    return jsonify({
        "status": "success",
        "message": "Login successful",
        "data": {
            "id": master.id,
            "name": master.name,
            "email": master.company_email,
            "panel_id": master.masteradminPanel.id
        },
        "token": {
            "access_token": access_token,
            "refresh_token": refresh_token
        }
    }), 200


@masterBP.route('/update', methods=['PUT'])
def update_master_admin():

    userID = g.user.get('userID') if g.user else None
    if not userID:
        return jsonify({
            "status" : "Error",
            "status" : "Unauthorized",
        }), 400
    
    try:

        data = request.get_json()
        if not g.user or g.user.get("role") != "master_admin":
            return jsonify({"status": "error", "message": "Unauthorized"}), 403

        master = Master.query.filter_by(id=userID).first()

        if not master:
            return jsonify({"status": "error", "message": "Master admin not found"}), 404

        name = data.get("name")
        email = data.get("company_email")
        new_password = data.get("new_password")
        current_password = data.get("current_password")

        if name:
            master.name = name

        if email:
            existing_email = Master.query.filter(
                Master.company_email == email,
                Master.id != userID
            ).first()
            if existing_email:
                return jsonify({"status": "error", "message": "Email already in use"}), 400
            master.company_email = email

        if new_password:
            if not current_password or not check_password_hash(master.company_password, current_password):
                return jsonify({"status": "error", "message": "Current password is incorrect"}), 401
            master.company_password = generate_password_hash(new_password)

        db.session.commit()

        return jsonify({
            "status": "success",
            "message": "Master admin profile updated",
            "data": {
                "id": master.id,
                "name": master.name,
                "email": master.company_email
            }
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({
            "status": "error",
            "message": "Something went wrong while updating profile",
            "error": str(e)
        }), 500
