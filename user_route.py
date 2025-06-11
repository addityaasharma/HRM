from werkzeug.security import generate_password_hash, check_password_hash
from models import User,UserPanelData,db,SuperAdmin,PunchData, UserTicket
from flask import Blueprint, request, json, jsonify, g
from otp_utils import generate_otp, send_otp
from middleware import create_tokens
from datetime import datetime
from dotenv import load_dotenv
from redis import Redis
import random,os
import string


user = Blueprint('user',__name__, url_prefix='/user')

def gen_empId():
    random_letter = random.choice(string.ascii_uppercase)
    last_user = User.query.filter(User.empId.like('%EMP%')).order_by(User.id.desc()).first()

    if last_user and last_user.empId:
        try:
            last_number = int(last_user.empId[-4:])
        except ValueError:
            last_number = 0
        new_number = last_number + 1
    else:
        new_number = 1

    return f"{random_letter}EMP{str(new_number).zfill(4)}"

load_dotenv()
REDIS_URL = os.getenv("REDIS_URL")
redis = Redis.from_url(REDIS_URL)

@user.route('/signup', methods=['POST'])
def send_otp_route():
    data = request.json
    required_fields = ['userName', 'email', 'password', 'superadminId','userRole', 'gender']
    if not all(field in data for field in required_fields):
        return jsonify({'error': 'Missing required fields'}), 400

    email = data['email']

    if User.query.filter_by(email=email).first():
        return jsonify({'error': 'User already exists'}), 409

    if not SuperAdmin.query.filter_by(superId=data['superadminId']).first():
        return jsonify({'error': 'Invalid superadmin ID'}), 404

    otp = generate_otp()
    otp_sent = send_otp(email, otp)
    print(f"{otp} and {otp_sent}")

    if not otp_sent:
        return jsonify({'error': 'Failed to send OTP'}), 500

    redis.setex(f"otp:{email}", 300, otp)
    redis.setex(f"signup:{email}", 300, json.dumps(data))

    return jsonify({'status': 'success', 'message': 'OTP sent successfully'}), 200


@user.route('/verify-signup', methods=['POST'])
def verify_otp_route():
    data = request.json
    email = data.get('email')
    otp_input = data.get('otp')

    stored_otp = redis.get(f"otp:{email}")
    if not stored_otp or stored_otp.decode() != otp_input:
        return jsonify({'error': 'Invalid or expired OTP'}), 400

    stored_data = redis.get(f"signup:{email}")
    if not stored_data:
        return jsonify({'error': 'Signup data expired or missing'}), 400

    user_data = json.loads(stored_data)

    superadmin = SuperAdmin.query.filter_by(superId=user_data['superadminId']).first()
    if not superadmin or not superadmin.superadminPanel:
        return jsonify({'error': 'SuperAdmin panel not found'}), 404
    
    new_user = User(
        superadminId=user_data['superadminId'],
        empId=gen_empId(),
        userName=user_data['userName'],
        email=user_data['email'],
        gender = user_data['gender'],
        password=generate_password_hash(user_data['password']),
        onBoardingStatus=user_data.get('onBoardingStatus'),
        profileImage=user_data.get('profileImage'),
        department=user_data.get('department'),
        sourceOfHire=user_data.get('sourceOfHire'),
        panNumber=user_data.get('panNumber'),
        adharNumber=user_data.get('adharNumber'),
        uanNumber=user_data.get('uanNumber'),
        userRole=user_data.get('userRole'),
        nationality=user_data.get('nationality'),
        number=user_data.get('number'),
        currentAddress=user_data.get('currentAddress'),
        permanentAddress=user_data.get('permanentAddress'),
        postal=user_data.get('postal'),
        city=user_data.get('city'),
        state=user_data.get('state'),
        country=user_data.get('country'),
        schoolName=user_data.get('schoolName'),
        degree=user_data.get('degree'),
        fieldOfStudy=user_data.get('fieldOfStudy'),
        currentSalary=user_data.get('currentSalary'),
        dateOfCompletion=user_data.get('dateOfCompletion'),
        skills=user_data.get('skills'),
        joiningDate=datetime.strptime(user_data.get('joiningDate'), '%Y-%m-%d') if user_data.get('joiningDate') else datetime.utcnow(),
        occupation=user_data.get('occupation'),
        company=user_data.get('company'),
        experience=user_data.get('experience'),
        duration=datetime.strptime(user_data.get('duration'), '%Y-%m-%d') if user_data.get('duration') else None,
        superadmin_panel_id=superadmin.superadminPanel.id,  # required for foreign key
    )

    db.session.add(new_user)
    db.session.flush() 

    new_user.panelData = UserPanelData()
    db.session.commit()

    access_token, refresh_token = create_tokens(user_id=new_user.id, role=new_user.userRole)

    redis.delete(f"otp:{email}")
    redis.delete(f"signup:{email}")

    return jsonify({
        'status': 'success',
        'message': 'User verified and created successfully',
        'user_id': new_user.id,
        'empId': new_user.empId,
        "userRole": new_user.userRole,
        'panelData_id': new_user.panelData.id,
        'access_token': access_token,
        "refresh_token": refresh_token,
    }), 201
        

@user.route('/login', methods=['POST'])
def user_login():
    data = request.json

    required_fields = ['email', 'password']
    if not all(field in data for field in required_fields):
        return jsonify({'message': 'All fields are required'}), 400

    user = User.query.filter_by(email=data['email']).first()
    if not user:
        return jsonify({'message': 'No user found'}), 404

    if not check_password_hash(user.password, data['password']):
        return jsonify({'message': 'Invalid Password'}), 401

    access_token, refresh_token = create_tokens(user_id=user.id, role=user.userRole)

    user_data = {
        'id': user.id,
        'userName': user.userName,
        'email': user.email,
        'empId': user.empId,
        'userRole': user.userRole,
        'profileImage': user.profileImage,
        'superadminId': user.superadminId
        # Add more fields if needed
    }

    return jsonify({
        'status': 'success',
        'message': "Login Successfully",
        'data': user_data,
        'token': {
            'access_token': access_token,
            'refresh_token': refresh_token
        }
    }), 200


@user.route('/punchin',methods=['POST'])
def punch_details():
    if request.method == 'POST':
        try:
            userId = g.user.get('userID') if g.user else None
            if not userId:
                return jsonify({
                    'message': 'User id is missing'
                }), 400

            user = User.query.filter_by(id=userId).first()
            if not user:
                return jsonify({
                    'message': 'No user found with this id'
                }), 404
        
            usersPanelData = user.panelData
            if not usersPanelData:
                return jsonify({
                    'status': 'error',
                    'message': 'No user panel data found'
                }), 404

            data = request.get_json()
            if not data:
                return jsonify({
                    'status': 'error',
                    'message': 'No input data provided'
                }), 400

            required_fields = ['login', 'location']
            if not all(field in data for field in required_fields):
                return jsonify({
                    'status': 'error',
                    'message': 'All fields are required',
                }), 400

            try:
                login_time = datetime.fromisoformat(data.get('login'))
            except Exception:
                return jsonify({
                    'status': 'error',
                    'message': 'Invalid datetime format for login'
                }), 400

            punchin = PunchData(
                panelData=usersPanelData.id,
                empId=user.empId,
                name=user.userName,
                email=user.email,
                login=login_time,
                logout=None,
                location=data.get('location'),
                totalhour=None,
                productivehour=None,
                shift=None,
                status="present"
            )

            db.session.add(punchin)
            db.session.commit()

            return jsonify({
                'status': 'success',
                'message': 'Punch-in successful',
                'punch_id': punchin.id
            }), 201

        except Exception as e:
            db.session.rollback()
            return jsonify({
                'message': 'Error processing punch-in',
                'error': str(e)
            }), 500

    else:
        return jsonify({'message': 'Method not allowed'}), 405


@user.route('/punchin/<int:punchId>',methods=['PUT'])
def edit_punchDetails(punchId):
    data = request.get_json()
    if not data:
        return jsonify({
            "status": "error",
            "message": "No data found"
        }), 400

    required_fields = ['logout', 'location', 'totalhour', 'productivehour', 'status']
    if not all(field in data for field in required_fields):
        return jsonify({
            "status": "error",
            "message": "Missing or invalid fields"
        }), 400

    try:
        userID = g.user.get('userID') if g.user else None
        if not userID:
            return jsonify({
                "status": "error",
                "message": "No user or auth token found"
            }), 401

        user = User.query.filter_by(id=userID).first()
        if not user:
            return jsonify({
                "status": "error",
                "message": "No user found with this ID"
            }), 404

        punchdata = PunchData.query.filter_by(id=punchId).first()
        if not punchdata:
            return jsonify({
                "status": "error",
                "message": "No punch details found with this ID"
            }), 404

        # Update fields
        punchdata.logout = data['logout']
        punchdata.location = data['location']
        punchdata.totalhour = data['totalhour']
        punchdata.productivehour = data['productivehour']
        punchdata.status = data['status']

        db.session.commit()

        return jsonify({
            "status": "success",
            "message": "Punch details updated successfully"
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({
            "status": "error",
            "message": "Internal Server Error",
            "error": str(e)
        }), 500

    
@user.route('/edit_details', methods=['PUT'])
def edit_details():
    try:
        userId = g.user.get('userID') if g.user else None
        if not userId:
            return jsonify({
                'status': 'error',
                'message': 'No auth token provided or user not found.'
            }), 400

        user = User.query.filter_by(id=userId).first()
        if not user:
            return jsonify({
                'status': 'error',
                'message': 'User not found.'
            }), 404

        data = request.get_json()
        if not data:
            return jsonify({
                'status': 'error',
                'message': 'No data provided.'
            }), 400

        updatable_fields = [
            'profileImage', 'userName', 'gender', 'number',
            'currentAddress', 'permanentAddress', 'postal', 'city',
            'state', 'country', 'nationality', 'panNumber',
            'adharNumber', 'uanNumber', 'department', 'onBoardingStatus',
            'sourceOfHire', 'currentSalary', 'joiningDate', 'schoolName',
            'degree', 'fieldOfStudy', 'dateOfCompletion', 'skills',
            'occupation', 'company', 'experience', 'duration'
        ]

        for field in updatable_fields:
            if field in data:
                if field == 'joiningDate' or field == 'dateOfCompletion':
                    try:
                        setattr(user, field, datetime.strptime(data[field], '%Y-%m-%d').date())
                    except ValueError:
                        return jsonify({
                            'status': 'error',
                            'message': f'Invalid date format for {field}. Use YYYY-MM-DD.'
                        }), 400
                else:
                    setattr(user, field, data[field])

        db.session.commit()

        return jsonify({
            'status': 'success',
            'message': 'User details updated successfully.'
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({
            'status': 'error',
            'message': 'Internal Server Error',
            'error': str(e)
        }), 500


@user.route('/raise_ticket')
def raise_ticket():
    data = request.get_json()
    if not data:
        return jsonify({
            'status': 'error',
            'message': 'No data found'
        }), 400

    required_fields = ['topic', 'problem', 'priority', 'department', 'document']
    if not all(field in data for field in required_fields):
        return jsonify({
            'status': 'error',
            'message': "All fields are required"
        }), 400

    try:
        user_id = g.user.get('userID') if g.user else None
        if not user_id:
            return jsonify({
                'status': 'error',
                'message': 'No auth token or userID found'
            }), 401

        user = User.query.filter_by(id=user_id).first()
        if not user or not user.panelData:
            return jsonify({
                'status': 'error',
                'message': 'User or user panel data not found'
            }), 404

        ticket = UserTicket(
            userName=user.userName,
            userId=user.empId,
            date=datetime.utcnow(),
            topic=data['topic'],
            problem=data['problem'],
            priority=data['priority'],
            department=data['department'],
            document=data['document'],
            status='pending',
            userticketpanel=user.panelData.id
        )

        db.session.add(ticket)
        db.session.commit()

        return jsonify({
            'status': 'success',
            'message': 'Ticket raised successfully',
            'ticket': {
                'ticketId': ticket.id,
                'topic': ticket.topic,
                'priority': ticket.priority,
                'status': ticket.status
            }
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({
            'status': 'error',
            'message': 'Internal server error',
            'error': str(e)
        }), 500
