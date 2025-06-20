from models import User,UserPanelData,db,SuperAdmin,PunchData, UserTicket, UserDocument, UserChat, UserLeave, ShiftTimeManagement, Announcement, Likes, Comments, Notice, ProductAsset
from werkzeug.security import generate_password_hash, check_password_hash
from flask import Blueprint, request, json, jsonify, g
from datetime import datetime,time, timedelta
from otp_utils import generate_otp, send_otp
from flask_socketio import join_room, emit
from sqlalchemy import func, extract, and_
from socket_instance import socketio
from middleware import create_tokens
from dotenv import load_dotenv
from config import cloudinary
import cloudinary.uploader
from redis import Redis
import random,os
import string, math


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

# ====================================
#          USER AUTH SECTION
# ====================================

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


# ====================================
#          USER PUNCH SECTION
# ====================================

@user.route('/punchin', methods=['POST'])
def punch_details():
    try:
        login = request.form.get('login')
        location = request.form.get('location')
        image_file = request.files.get('image')

        if not login or not location or not image_file:
            return jsonify({
                'status': 'error',
                'message': 'All fields (login, location, image) are required'
            }), 400

        userId = g.user.get('userID') if g.user else None
        if not userId:
            return jsonify({'status': 'error', 'message': 'User not authenticated'}), 400

        user = User.query.filter_by(id=userId).first()
        if not user:
            return jsonify({'status': 'error', 'message': 'No user found'}), 404

        superadmin = SuperAdmin.query.filter_by(superId=user.superadminId).first()
        if not superadmin:
            return jsonify({'status': 'error', 'message': 'Unauthorized user'}), 403

        usersPanelData = user.panelData
        if not usersPanelData:
            return jsonify({'status': 'error', 'message': 'User panel data not found'}), 404

        try:
            login_time = datetime.fromisoformat(login)
        except Exception:
            return jsonify({'status': 'error', 'message': 'Invalid login time format'}), 400

        today_start = datetime.combine(login_time.date(), datetime.min.time())
        today_end = datetime.combine(login_time.date(), datetime.max.time())

        existing_punch = PunchData.query.filter(
            PunchData.empId == user.empId,
            PunchData.login >= today_start,
            PunchData.login <= today_end
        ).first()

        if existing_punch:
            return jsonify({
                'status': 'error',
                'message': 'You have already punched in today.'
            }), 409

        shift = ShiftTimeManagement.query.filter_by(
            shiftType=user.shift,
            shiftStatus='enable',
            superpanel=superadmin.superadminPanel.id
        ).first()

        if not shift:
            return jsonify({
                'status': 'error',
                'message': f'No active {user.shift} shift set by admin'
            }), 404

        try:
            upload_result = cloudinary.uploader.upload(image_file)
            image_url = upload_result.get('secure_url')
        except Exception as e:
            return jsonify({
                'status': 'error',
                'message': 'Image upload failed',
                'error': str(e)
            }), 500

        max_early = shift.MaxEarly
        grace_time = shift.GraceTime
        max_late = shift.MaxLateEntry

        if login_time < max_early:
            return jsonify({
                'status': 'error',
                'message': 'Too early to punch in'
            }), 403

        if login_time <= grace_time:
            punch_status = 'ontime'
        elif login_time <= max_late:
            punch_status = 'late'
        else:
            punch_status = 'halfday'

        # Save punch-in
        punchin = PunchData(
            panelData=usersPanelData.id,
            empId=user.empId,
            name=user.userName,
            email=user.email,
            login=login_time,
            logout=None,
            location=location,
            totalhour=None,
            productivehour=None,
            shift=shift.shiftStart,
            status=punch_status,
            image=image_url
        )

        db.session.add(punchin)
        db.session.commit()

        return jsonify({
            'status': 'success',
            'message': f'Punch-in successful. Status: {punch_status}',
            'punch_id': punchin.id,
            'image_url': image_url
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({
            'status': 'error',
            'message': 'Error processing punch-in',
            'error': str(e)
        }), 500


@user.route('/punchin', methods=['GET'])
def get_punchDetails():
    try:
        userID = g.user.get('userID') if g.user else None
        if not userID:
            return jsonify({
                "status": "error",
                "message": "No user found or auth token provided"
            }), 404

        user = User.query.filter_by(id=userID).first()
        if not user:
            return jsonify({
                "status": "error",
                "message": "No user found"
            }), 404

        panel_data = user.panelData
        if not panel_data:
            return jsonify({
                "status": "error",
                "message": "User panel data not found"
            }), 404

        punchdetails = panel_data.userPunchData
        if not punchdetails:
            return jsonify({
                "status": "error",
                "message": "No punch records found"
            }), 404

        punch_list = []
        for punch in punchdetails:
            punch_list.append({
                "id": punch.id,
                "image": punch.image,
                "empId": punch.empId,
                "name": punch.name,
                "email": punch.email,
                "login": punch.login.isoformat() if punch.login else None,
                "logout": punch.logout.isoformat() if punch.logout else None,
                "location": punch.location,
                "status": punch.status,
                "totalhour": punch.totalhour if isinstance(punch.totalhour, str) else punch.totalhour.strftime('%H:%M:%S') if punch.totalhour else None,
                "productivehour": punch.productivehour.isoformat() if punch.productivehour else None,
                "shift": punch.shift.isoformat() if punch.shift else None
            })

        return jsonify({
            "status": "success",
            "message": "Punch details fetched successfully",
            "data": punch_list
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({
            "status": "error",
            "message": "Internal Server Error",
            "error": str(e)
        }), 500


@user.route('/punchin/<int:punchId>', methods=['PUT'])
def edit_punchDetails(punchId):
    data = request.get_json()
    if not data:
        return jsonify({
            "status": "error",
            "message": "No data found"
        }), 400

    required_fields = ['logout', 'location', 'totalHour']
    if not all(field in data for field in required_fields):
        return jsonify({
            "status": "error",
            "message": "Missing or invalid fields"
        }), 400

    try:
        logout_time = datetime.fromisoformat(data.get('logout').replace('Z', '+00:00'))

        total_hour_str = data.get('totalHour')
        try:
            h, m, s = map(int, total_hour_str.strip().split(':'))
            total_hour_time = time(hour=h, minute=m, second=s)
        except ValueError:
            return jsonify({
                "status": "error",
                "message": "Invalid format for totalHour. Expected HH:MM:SS"
            }), 400

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

        punchdata = PunchData.query.filter_by(id=punchId, empId=user.empId).first()
        if not punchdata:
            return jsonify({
                "status": "error",
                "message": "No punch details found with this ID"
            }), 404

        superadmin = SuperAdmin.query.filter_by(superId=user.superadminId).first()
        if not superadmin:
            return jsonify({
                "status": "error",
                "message": "Unauthorized user"
            }), 403

        shift = ShiftTimeManagement.query.filter_by(
            shiftType=user.shift,
            shiftStatus='enable',
            superpanel=superadmin.superadminPanel.id
        ).first()

        if not shift:
            return jsonify({
                "status": "error",
                "message": f"No active {user.shift} shift set by admin"
            }), 404

        logout_date = logout_time.date()
        shift_end_time = datetime.combine(logout_date, shift.shiftEnd)

        if logout_time < shift_end_time:
            punch_status = 'halfday'
        else:
            punch_status = 'fullday'

        punchdata.logout = logout_time
        punchdata.location = data['location']
        punchdata.totalhour = total_hour_time
        punchdata.status = punch_status

        db.session.commit()

        return jsonify({
            "status": "success",
            "message": f"Punch details updated successfully. Status: {punch_status}"
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({
            "status": "error",
            "message": "Internal Server Error",
            "error": str(e)
        }), 500


# ====================================
#        USER DETAILS SECTION
# ====================================


@user.route('/profile', methods=['GET'])
def get_Profile():
    try:
        userId = g.user.get('userID') if g.user else None
        if not userId:
            return jsonify({
                "status": "error",
                "message": "No user ID or auth token provided",
            }), 400

        user = User.query.filter_by(id=userId).first()
        if not user:
            return jsonify({
                "status": "error",
                "message": "No user found"
            }), 404

        userDetails = {
            'id': user.id,
            'profileImage': user.profileImage,
            'superadminId': user.superadminId,
            'userName': user.userName,
            'empId': user.empId,
            'email': user.email,
            'gender': user.gender,
            'number': user.number,
            'currentAddress': user.currentAddress,
            'permanentAddress': user.permanentAddress,
            'postal': user.postal,
            'city': user.city,
            'state': user.state,
            'country': user.country,
            'nationality': user.nationality,
            'panNumber': user.panNumber,
            'adharNumber': user.adharNumber,
            'uanNumber': user.uanNumber,
            'department': user.department,
            'onBoardingStatus': user.onBoardingStatus,
            'sourceOfHire': user.sourceOfHire,
            'currentSalary': user.currentSalary,
            'joiningDate': user.joiningDate.strftime("%Y-%m-%d") if user.joiningDate else None,
            'schoolName': user.schoolName,
            'degree': user.degree,
            'fieldOfStudy': user.fieldOfStudy,
            'dateOfCompletion': user.dateOfCompletion.strftime("%Y-%m-%d") if user.dateOfCompletion else None,
            'skills': user.skills,
            'shift': user.shift,
            'occupation': user.occupation,
            'company': user.company,
            'experience': user.experience,
            'duration': user.duration,
            'userRole': user.userRole,
            'managerId': user.managerId,
            'superadmin_panel_id': user.superadmin_panel_id,
            'created_at': user.created_at.strftime("%Y-%m-%d %H:%M:%S") if user.created_at else None
        }

        return jsonify({
            "status": "success",
            "message": "Fetched successfully",
            "data": userDetails
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({
            "status": "error",
            "message": "Internal Server Error",
            "error": str(e)
        }), 500


@user.route('/profile', methods=['PUT'])
def edit_Profile():
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

        data = request.form.to_dict()
        file = request.files.get('profileImage')

        updatable_fields = [
            'userName', 'gender', 'number', 'currentAddress', 'permanentAddress',
            'postal', 'city', 'state', 'country', 'nationality', 'panNumber',
            'adharNumber', 'uanNumber', 'department', 'onBoardingStatus',
            'sourceOfHire', 'currentSalary', 'joiningDate', 'schoolName',
            'degree', 'fieldOfStudy', 'dateOfCompletion', 'skills',
            'occupation', 'company', 'experience', 'duration', 'birthday'
        ]

        if file:
            upload_result = cloudinary.uploader.upload(file, folder="user_profiles")
            user.profileImage = upload_result.get("secure_url")

        for field in updatable_fields:
            if field in data:
                if field in ['joiningDate', 'dateOfCompletion', 'birthday']:
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


# ====================================
#        USER TICKET SECTION
# ====================================


@user.route('/ticket', methods=['POST'])
def raise_ticket():
    data = request.get_json()
    if not data:
        return jsonify({
            'status': 'error',
            'message': 'No data found'
        }), 400

    required_fields = ['topic', 'problem', 'priority', 'department']
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
            document=None,
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


@user.route('/ticket', methods=['GET'])
def get_ticket():
    try:
        userID = g.user.get('userID') if g.user else None
        if not userID:
            return jsonify({"status": "error", "message": "No user ID found"}), 404

        user = User.query.filter_by(id=userID).first()
        if not user:
            return jsonify({"status": "error", "message": "No user found with this ID"}), 400

        panel_data = user.panelData
        if not panel_data:
            return jsonify({"status": "error", "message": "User panel data not found"}), 404

        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 10))
        offset = (page - 1) * limit

        all_tickets = panel_data.UserTicket
        total_tickets = len(all_tickets)
        paginated_tickets = all_tickets[offset:offset + limit]

        if not paginated_tickets:
            return jsonify({"status": "error", "message": "No tickets found on this page"}), 404

        ticket_list = []
        for ticket in paginated_tickets:
            ticket_list.append({
                "id": ticket.id,
                "userName": ticket.userName,
                "userId": ticket.userId,
                "date": ticket.date.isoformat() if ticket.date else None,
                "topic": ticket.topic,
                "problem": ticket.problem,
                "priority": ticket.priority,
                "department": ticket.department,
                "document": ticket.document,
                "status": ticket.status or 'pending'
            })

        return jsonify({
            "status": "success",
            "total": total_tickets,
            "page": page,
            "limit": limit,
            "total_pages": (page + total_tickets - 1),
            "message": "Fetched successfully",
            "data": ticket_list,
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({
            "status": "error",
            "message": "Internal Server Error",
            "error": str(e)
        }), 500


# ====================================
#        USER DOCUMENTS SECTION
# ====================================


@user.route('/documents', methods=['POST'])
def upload_documents():
    try:
        userID = g.user.get('userID') if g.user else None
        if not userID:
            return jsonify({"status": "error", "message": "No user or auth token provided"}), 404

        user = User.query.filter_by(id=userID).first()
        if not user or not user.panelData:
            return jsonify({"status": "error", "message": "User or panel data not found"}), 400

        file = request.files.get('document')
        if not file:
            return jsonify({"status": "error", "message": "No file found"}), 404

        title = request.form.get('title', '')

        result = cloudinary.uploader.upload(file)
        doc_url = result.get("secure_url")

        newDoc = UserDocument(
            documents=doc_url,
            panelDataID=user.panelData.id,
            title=title
        )
        db.session.add(newDoc)
        db.session.commit()

        return jsonify({
            "status": "success",
            "message": "Document uploaded successfully",
            "document": {
                "url": doc_url,
                "title": title
            }
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({
            "status": "error",
            "message": "Internal Server Error",
            "error": str(e)
        }), 500


@user.route('/documents', methods=['GET'])
def get_documents():
    try:
        userID = g.user.get('userID') if g.user else None
        if not userID:
            return jsonify({"status": "error", "message": "No user or auth token found"}), 404

        user = User.query.filter_by(id=userID).first()
        if not user:
            return jsonify({"status": "error", "message": "No user found with this id"}), 409

        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 10))

        documents = user.panelData.UserDocuments

        document_list = []
        for document in documents:
            document_list.append({
                'id': document.id,
                "documents": document.documents,
                "title": document.title,
            })

        return jsonify({
            "status": "success",
            "message": "Fetched successfully",
            "documents": document_list,
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({
            "status": "error",
            "message": "Internal Server Error",
            "error": str(e)
        }), 500


@user.route('/documents/<int:documentid>', methods=['PUT'])
def edit_documents(documentid):
    try:
        userID = g.user.get('userID') if g.user else None
        if not userID:
            return jsonify({"status": "error", "message": "No user or auth token provided"}), 404

        user = User.query.filter_by(id=userID).first()
        if not user or not user.panelData:
            return jsonify({"status": "error", "message": "User or panel data not found"}), 400

        document = UserDocument.query.filter_by(id=documentid, panelDataID=user.panelData.id).first()
        if not document:
            return jsonify({"status": "error", "message": "No document found for this user"}), 404

        updated = False

        title = request.form.get('title')
        if title:
            document.title = title
            updated = True

        file = request.files.get('document')
        print('file',file)
        if file:
            result = cloudinary.uploader.upload(file)
            doc_url = result.get("secure_url")

            if not doc_url:
                return jsonify({"status": "error", "message": "Image upload failed"}), 500

            document.documents = doc_url
            updated = True

        if not updated:
            return jsonify({"status": "error", "message": "No changes submitted"}), 400

        db.session.commit()

        return jsonify({
            "status": "success",
            "message": "Document updated successfully",
            "document": {
                "id": document.id,
                "url": document.documents,
                "title": document.title
            }
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({
            "status": "error",
            "message": "Internal Server Error",
            "error": str(e)
        }), 500


@user.route('/documents/<int:document_id>', methods=['DELETE'])
def delete_document(document_id):
    try:
        userID = g.user.get('userID') if g.user else None
        if not userID:
            return jsonify({"status": "error", "message": "No user or auth token provided"}), 404

        user = User.query.filter_by(id=userID).first()
        if not user or not user.panelData:
            return jsonify({"status": "error", "message": "User or panel data not found"}), 400

        document = UserDocument.query.filter_by(id=document_id, panelDataID=user.panelData.id).first()
        if not document:
            return jsonify({"status": "error", "message": "Document not found or does not belong to user"}), 404

        db.session.delete(document)
        db.session.commit()

        return jsonify({
            "status": "success",
            "message": "Document deleted successfully"
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({
            "status": "error",
            "message": "Internal Server Error",
            "error": str(e)
        }), 500


# ====================================
#          USER SALARY SECTION
# ====================================

@user.route('/salary', methods=['GET'])
def salary_details():
    try:
        userID = g.user.get('userID') if g.user else None
        if not userID:
            return jsonify({"status" : "error", "message" : "No user_id or auth token provided"}), 404
        
        user = User.query.filter_by(id=userID).first()
        if not user:
            return jsonify({"status" : "error", "message" : "No user found"}), 409
        
        salaryDetails = user.panelData.userSalaryDetails
        if not salaryDetails:
            return jsonify({"status" : "error", "message" : "No salary details"}), 409
        
        salarylist=[]
        for salary in salaryDetails:
            salarylist.append({
                "id" : salary.id,
                "empId" : salary.empId,
                "present" : salary.present,
                "absent" : salary.absent,
                "basicSalary" : salary.basicSalary,
                "deductions" : salary.deductions,
                "finalPay" : salary.finalPay,
                "mode" : salary.mode,
                "status" : salary.status,
                "payslip" : salary.payslip,
                "approvedLeaves" : salary.approvedLeaves,
            })

        return jsonify({"status" : "success", "message" : "fetched Successfully", "data" : salarylist}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"status" : "error", "message" : "Internal Server Error", "error" : str(e)}), 500


# ====================================
#        USER CHAT SECTION
# ====================================


@user.route('/colleagues/<int:id>', methods=['GET'])
def all_users(id):
    try:
        userID = g.user.get('userID') if g.user else None
        if not userID:
            return jsonify({"status": "error", "message": "No user or auth token provided"}), 400

        user = User.query.filter_by(id=userID).first()
        if not user or not user.superadminId:
            return jsonify({"status": "error", "message": "No user or Admin found"}), 409

        adminID = user.superadminId
        superadmin = SuperAdmin.query.filter_by(superId=adminID).first()
        if not superadmin or not superadmin.superadminPanel or not superadmin.superadminPanel.allUsers:
            return jsonify({"status": "error", "message": "No Admin or users found associated with you"}), 404

        all_users = superadmin.superadminPanel.allUsers

        if id != 0:
            user_detail = next((u for u in all_users if u.id == id), None)
            if not user_detail:
                return jsonify({"status": "error", "message": "User not found"}), 404

            return jsonify({
                "status": "success",
                "user": {
                    'id': user_detail.id,
                    'userName': user_detail.userName,
                    'email': user_detail.email,
                    'empId': user_detail.empId,
                    'department': user_detail.department,
                    'source_of_hire': user_detail.sourceOfHire,
                    'PAN': user_detail.panNumber,
                    'UAN': user_detail.uanNumber,
                    'joiningDate': user_detail.joiningDate
                }
            }), 200

        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 10))
        start = (page - 1) * limit
        end = start + limit
        total_users = len(all_users)
        paginated_users = all_users[start:end]

        userList = []
        for u in paginated_users:
            userList.append({
                'id': u.id,
                'userName': u.userName,
                'email': u.email,
                'empId': u.empId,
                'department': u.department,
                'source_of_hire': u.sourceOfHire,
                'PAN': u.panNumber,
                'UAN': u.uanNumber,
                'joiningDate': u.joiningDate
            })

        return jsonify({
            "status": "success",
            "message": "Fetched successfully",
            "page": page,
            "limit": limit,
            "total_users": total_users,
            "total_pages": (total_users + limit - 1) // limit,
            "users": userList
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": "Internal Server Error", "error": str(e)}), 500


@user.route('/message', methods=['POST'])
def send_message():
    try:
        userID = g.user.get('userID') if g.user else None
        if not userID:
            return jsonify({"status": "error", "message": "No user or auth token provided"}), 404

        user = User.query.filter_by(id=userID).first()
        if not user:
            return jsonify({"status": "error", "message": "User not found"}), 400

        if not user.panelData:
            return jsonify({"status": "error", "message": "Panel data not found"}), 404

        data = request.get_json()
        required_fields = ['recieverID', 'message']
        if not all(field in data for field in required_fields):
            return jsonify({"status": "error", "message": "All fields are required"}), 400

        recieverId = data['recieverID']
        message_text = data['message']

        reciever = User.query.filter_by(id=recieverId).first()
        if not reciever:
            return jsonify({"status": "error", "message": "Receiver not found"}), 404

        superadmin = SuperAdmin.query.filter_by(superId=reciever.superadminId).first()
        if not superadmin:
            return jsonify({"status": "error", "message": "Receiver not found"}), 400

        message = UserChat(
            panelData=user.panelData.id,
            senderID=user.empId,
            recieverID=reciever.empId,
            message=message_text,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )

        db.session.add(message)
        db.session.commit()
        socketio.emit('receive_message', {
            'senderID': user.empId,
            'recieverID': reciever.empId,
            'message': message_text,
            'timestamp': str(message.created_at)
        }, room=recieverId)

        socketio.emit('message_sent', {'status': 'success'}, room=user.empId)

        return jsonify({"status": "success", "message": "Message sent"}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": "Internal Server Error", "error": str(e)}), 500
    

@user.route('/message/<string:with_empId>', methods=['GET'])
def get_chat_messages(with_empId):
    try:
        userID = g.user.get('userID') if g.user else None
        if not userID:
            return jsonify({"status": "error", "message": "No user or auth token provided"}), 404

        user = User.query.filter_by(id=userID).first()
        if not user or not user.panelData:
            return jsonify({"status": "error", "message": "User or panel data not found"}), 404

        sender_empId = user.empId

        chats = UserChat.query.filter(
            ((UserChat.senderID == sender_empId) & (UserChat.recieverID == with_empId)) |
            ((UserChat.senderID == with_empId) & (UserChat.recieverID == sender_empId))
        ).order_by(UserChat.created_at.asc()).all()

        messages = [{
            "id": chat.id,
            "senderID": chat.senderID,
            "receiverID": chat.recieverID,
            "message": chat.message,
            "created_at": chat.created_at.isoformat()
        } for chat in chats]

        return jsonify({"status": "success", "messages": messages}), 200

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": "Internal server error",
            "error": str(e)
        }), 500


# ====================================
#        USER LEAVE SECTION
# ====================================

@user.route('/leave', methods=['POST'])
def request_leave():
    data = request.get_json()
    if not data:
        return jsonify({"message": "No data provided", "status": "error"}), 400

    required_fields = ['empId', 'leavetype', 'leavefrom', 'leaveto', 'reason']
    if not all(field in data for field in required_fields):
        return jsonify({"status": "error", "message": "All fields are required"}), 400

    try:
        userID = g.user.get('userID') if g.user else None
        if not userID:
            return jsonify({"status": "error", "message": "No user or auth token provided"}), 409

        user = User.query.filter_by(id=userID).first()
        if not user:
            return jsonify({"status": "error", "message": "Invalid user"}), 404

        superadmin = SuperAdmin.query.filter_by(superId=user.superadminId).first()
        if not superadmin:
            return jsonify({"status": "error", "message": "Leave policy not set by admin"}), 409

        # FIX: Check if adminLeave list exists and is not empty
        if not hasattr(superadmin.superadminPanel, 'adminLeave') or not superadmin.superadminPanel.adminLeave:
            return jsonify({'status': "error", "message": "Admin has not configured any leave policies"}), 404
        
        adminLeaveDetails = superadmin.superadminPanel.adminLeave[0]
        print(adminLeaveDetails)

        # Date parsing
        leaveStart = datetime.strptime(data['leavefrom'], "%Y-%m-%d").date()
        leaveEnd = datetime.strptime(data['leaveto'], "%Y-%m-%d").date()
        totalDays = (leaveEnd - leaveStart).days + 1

        today = datetime.utcnow().date()
        currentMonth = today.month
        currentYear = today.year
        unpaidDays = 0

        # -------- Condition 1: Probation --------
        if adminLeaveDetails.probation:
                if not user.duration:
                    return jsonify({"status": "error", "message": "User resignation date not set"}), 400
                if (user.duration - today).days <= 30:
                    return jsonify({"status": "error", "message": "You can't apply for leave within 1 month of resignation"}), 403

        # -------- Condition 2: Lapse Policy --------
        previousYearLeaves = 0
        if not adminLeaveDetails.lapse_policy:
            previousYearLeaves = db.session.query(func.sum(UserLeave.days)).filter(
                UserLeave.empId == data['empId'],
                UserLeave.status == 'approved',
                UserLeave.from_date.between(f'{currentYear - 1}-01-01', f'{currentYear - 1}-12-31')
            ).scalar() or 0

        # -------- Condition 3: Calculation Type --------
        calc_type = adminLeaveDetails.calculationType
        start_range, end_range = None, None

        if calc_type == 'monthly':
            start_range = today.replace(day=1)
            if currentMonth == 12:
                end_range = today.replace(day=31)
            else:
                end_range = (today.replace(month=currentMonth + 1, day=1) - timedelta(days=1))

            prev_start = (today.replace(day=1) - timedelta(days=1)).replace(day=1)
            prev_end = prev_start.replace(day=28) + timedelta(days=4)
            prev_end = prev_end - timedelta(days=prev_end.day)

        elif calc_type == 'quarterly':
            start_month = 1 + 3 * ((currentMonth - 1) // 3)
            end_month = start_month + 2
            start_range = datetime(currentYear, start_month, 1).date()
            if end_month == 12:
                end_range = datetime(currentYear, 12, 31).date()
            else:
                end_range = (datetime(currentYear, end_month + 1, 1) - timedelta(days=1)).date()

            prev_start_month = start_month - 3 if start_month > 3 else 10
            prev_year = currentYear if start_month > 3 else currentYear - 1
            prev_start = datetime(prev_year, prev_start_month, 1).date()
            prev_end = (datetime(prev_year, prev_start_month + 3, 1) - timedelta(days=1)) if prev_start_month < 10 else datetime(prev_year, 12, 31).date()

        elif calc_type == 'yearly':
            start_range = datetime(currentYear, 1, 1).date()
            end_range = datetime(currentYear, 12, 31).date()
            prev_start = datetime(currentYear - 1, 1, 1).date()
            prev_end = datetime(currentYear - 1, 12, 31).date()

        # -------- Carryforward Logic --------
        carried_forward = 0
        if adminLeaveDetails.carryforward:
            prev_taken = db.session.query(func.sum(UserLeave.days)).filter(
                UserLeave.empId == data['empId'],
                UserLeave.status == 'approved',
                and_(
                    UserLeave.leavefrom >= prev_start,
                    UserLeave.leavefrom <= prev_end
                )
            ).scalar() or 0

            prev_allowance = adminLeaveDetails.max_leave_once
            if calc_type == 'yearly':
                prev_allowance = adminLeaveDetails.max_leave_year

            unused = max(prev_allowance - prev_taken, 0)
            carried_forward = unused

        # -------- Leave Taken in Current Cycle --------
        cycle_taken = db.session.query(func.sum(UserLeave.days)).filter(
            UserLeave.empId == data['empId'],
            UserLeave.status == 'approved',
            and_(
                UserLeave.leavefrom >= start_range,
                UserLeave.leavefrom <= end_range
            )
        ).scalar() or 0

        cycle_limit = adminLeaveDetails.max_leave_once
        if calc_type == 'yearly':
            cycle_limit = adminLeaveDetails.max_leave_year

        total_available = cycle_limit + carried_forward
        if cycle_taken + totalDays > total_available:
            unpaidDays += (cycle_taken + totalDays) - total_available

        # -------- NEW CONDITION: Monthly Leave Limit with Carryover --------
        if hasattr(adminLeaveDetails, 'monthly_leave_limit') and adminLeaveDetails.monthly_leave_limit:
            monthly_limit = adminLeaveDetails.monthly_leave_limit  # e.g., 2 leaves per month
            
            # Calculate current month range based on leave start date, not today's date
            leave_month = leaveStart.month
            leave_year = leaveStart.year
            
            current_month_start = datetime(leave_year, leave_month, 1).date()
            if leave_month == 12:
                current_month_end = datetime(leave_year, 12, 31).date()
            else:
                current_month_end = (datetime(leave_year, leave_month + 1, 1) - timedelta(days=1)).date()
            
            # Calculate previous month range
            if leave_month == 1:
                prev_month_start = datetime(leave_year - 1, 12, 1).date()
                prev_month_end = datetime(leave_year - 1, 12, 31).date()
            else:
                prev_month_start = datetime(leave_year, leave_month - 1, 1).date()
                if leave_month - 1 == 2:  # February
                    prev_month_end = datetime(leave_year, leave_month - 1, 28).date()
                    if leave_year % 4 == 0 and (leave_year % 100 != 0 or leave_year % 400 == 0):
                        prev_month_end = datetime(leave_year, leave_month - 1, 29).date()
                else:
                    prev_month_end = (datetime(leave_year, leave_month, 1) - timedelta(days=1)).date()
            
            # Get current month PAID leaves taken (approved leaves only)
            current_month_leaves = db.session.query(UserLeave.days, UserLeave.unpaidDays).filter(
                UserLeave.empId == data['empId'],
                UserLeave.status == 'approved',
                and_(
                    UserLeave.leavefrom >= current_month_start,
                    UserLeave.leavefrom <= current_month_end
                )
            ).all()
            
            current_month_paid_taken = 0
            for leave_days, unpaid_days in current_month_leaves:
                paid_days = leave_days - (unpaid_days or 0)
                current_month_paid_taken += paid_days
            
            # Get previous month leaves taken
            prev_month_taken = db.session.query(func.sum(UserLeave.days)).filter(
                UserLeave.empId == data['empId'],
                UserLeave.status == 'approved',
                and_(
                    UserLeave.leavefrom >= prev_month_start,
                    UserLeave.leavefrom <= prev_month_end
                )
            ).scalar() or 0
            
            # Calculate available monthly leaves with carryover
            prev_month_unused = max(monthly_limit - prev_month_taken, 0)
            total_monthly_available = monthly_limit + prev_month_unused
            
            # Debug prints
            print(f"Monthly Limit Debug:")
            print(f"Monthly limit: {monthly_limit}")
            print(f"Current month PAID taken: {current_month_paid_taken}")
            print(f"Previous month taken: {prev_month_taken}")
            print(f"Previous month unused: {prev_month_unused}")
            print(f"Total monthly available: {total_monthly_available}")
            print(f"Current request days: {totalDays}")
            
            # Calculate monthly unpaid days
            if current_month_paid_taken >= total_monthly_available:
                # User has already exhausted monthly limit - ALL current leave days are unpaid
                monthly_unpaid = totalDays
                print(f"Case 1: All days unpaid = {monthly_unpaid}")
            elif current_month_paid_taken + totalDays > total_monthly_available:
                # User will exceed monthly limit with this request
                monthly_unpaid = (current_month_paid_taken + totalDays) - total_monthly_available
                print(f"Case 2: Partial unpaid = {monthly_unpaid}")
            else:
                # User is within monthly limit
                monthly_unpaid = 0
                print(f"Case 3: No unpaid days = {monthly_unpaid}")
            
            unpaidDays = max(unpaidDays, monthly_unpaid)
            print(f"Final unpaid days: {unpaidDays}")

        # -------- Condition 4: Max Leave in Year --------
        yearlyLeaveTaken = db.session.query(func.sum(UserLeave.days)).filter(
            UserLeave.empId == user.empId,
            UserLeave.status == 'approved',
            extract('year', UserLeave.leavefrom) == currentYear
        ).scalar() or 0

        if yearlyLeaveTaken + totalDays > adminLeaveDetails.max_leave_year:
            yearly_unpaid = (yearlyLeaveTaken + totalDays) - adminLeaveDetails.max_leave_year
            unpaidDays = max(unpaidDays, yearly_unpaid)

        # -------- Save User Leave Request --------
        newLeave = UserLeave(
            panelData=user.panelData.id,
            empId=data['empId'],
            leavetype=data['leavetype'],
            leavefrom=leaveStart,
            leaveto=leaveEnd,
            reason=data['reason'],
            name=user.userName,
            email=user.email,
            days=totalDays,
            status='pending',
            unpaidDays=max(unpaidDays, 0),
        )

        db.session.add(newLeave)
        db.session.commit()

        return jsonify({"status": "success", "message": "Leave Sent Successfully"}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": "Internal Server Error", "error": str(e)}), 500


@user.route('/leave', methods=['GET'])
def get_leave_details():
    try:
        userID = g.user.get('userID') if g.user else None
        if not userID:
            return jsonify({"status": "error", "message": "No user or auth token provided"}), 409

        user = User.query.filter_by(id=userID).first()
        if not user:
            return jsonify({"status": "error", "message": "User not found"}), 404

        # Pagination & filtering inputs
        page = request.args.get('page', default=1, type=int)
        limit = request.args.get('limit', default=10, type=int)
        status = request.args.get('status', type=str)
        offset = (page - 1) * limit

        all_leaves = user.panelData.userLeaveData
        if status:
            all_leaves = [leave for leave in all_leaves if leave.status == status]

        all_leaves = sorted(all_leaves, key=lambda x: x.createdAt or datetime.min, reverse=True)

        total_records = len(all_leaves)
        total_pages = math.ceil(total_records / limit)

        total_days = sum([leave.days for leave in all_leaves])
        unpaid_total = sum([leave.unpaidDays for leave in all_leaves if leave.unpaidDays])

        paginated_leaves = all_leaves[offset:offset + limit]

        leave_list = []
        for leave in paginated_leaves:
            leave_list.append({
                "id": leave.id,
                "leaveType": leave.leavetype,
                "leaveFrom": leave.leavefrom.strftime('%Y-%m-%d'),
                "leaveTo": leave.leaveto.strftime('%Y-%m-%d'),
                "days": leave.days,
                "unpaidDays": leave.unpaidDays,
                "status": leave.status,
                "reason": leave.reason,
                "appliedOn": leave.createdAt.strftime('%Y-%m-%d') if leave.createdAt else 'By Mistake'
            })

        return jsonify({
            "status": "success",
            "message": "Leave history fetched successfully",
            "summary": {
                "totalLeaves": total_days,
                "unpaidLeaves": unpaid_total,
                "recordCount": total_records
            },
            "pagination": {
                "page": page,
                "limit": limit,
                "totalPages": total_pages,
                "hasMore": page < total_pages
            },
            "data": leave_list
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": "Internal Server Error", "error": str(e)}), 500


# ====================================
#   USER ANNOUNCE AND POLL SECTION
# ====================================


@user.route('/poll', methods=['POST'])
def check_pole():
    try:
        userID = g.user.get('userID') if g.user else None
        if not userID:
            return jsonify({
                "status": "error",
                "message": "No user or auth token provided",
            }), 404

        user = User.query.filter_by(id=userID).first()
        if not user:
            return jsonify({
                "status": "error",
                "message": "User not found",
            }), 404

        data = request.get_json()
        announcement_id = data.get('announcement_id')
        selected_option = data.get('selected_option')

        if not announcement_id or selected_option is None:
            return jsonify({
                "status": "error",
                "message": "Announcement ID and selected_option are required",
            }), 400

        announcement = Announcement.query.filter_by(id=announcement_id).first()
        if not announcement:
            return jsonify({
                "status": "error",
                "message": "Announcement not found",
            }), 404

        if selected_option == 1 and announcement.poll_option_1:
            announcement.votes_option_1 += 1
        elif selected_option == 2 and announcement.poll_option_2:
            announcement.votes_option_2 += 1
        elif selected_option == 3 and announcement.poll_option_3:
            announcement.votes_option_3 += 1
        elif selected_option == 4 and announcement.poll_option_4:
            announcement.votes_option_4 += 1
        else:
            return jsonify({
                "status": "error",
                "message": "Selected option is invalid or not available",
            }), 400

        db.session.commit()

        return jsonify({
            "status": "success",
            "message": "Your vote was recorded successfully"
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({
            "status": "error",
            "message": "Internal Server Error",
            "error": str(e)
        }), 500


@user.route('/announcement', methods=['GET'])
def get_announcement():
    try:
        userID = g.user.get('userID') if g.user else None
        if not userID:
            return jsonify({
                "status": "error",
                "message": "No user or auth token",
            }), 404

        user = User.query.filter_by(id=userID).first()
        if not user:
            return jsonify({
                "status": "error",
                "message": "No user found",
            }), 404

        useradmin = SuperAdmin.query.filter_by(superId=user.superadminId).first()
        if not useradmin:
            return jsonify({
                "status": "error",
                "message": "Unauthorized",
            }), 409

        allAnnouncement = useradmin.superadminPanel.adminAnnouncement

        result = []
        for ann in allAnnouncement:
            if not ann.is_published:
                continue
            if ann.scheduled_time and ann.scheduled_time > datetime.utcnow():
                continue

            liked_by_user = Likes.query.filter_by(
                announcement_id=ann.id,
                empId=userID
            ).first() is not None

            comment_list = [{
                "id": c.id,
                "empId": c.empId,
                "comment": c.comments,
                "created_at": c.created_at.isoformat()
            } for c in ann.comments]

            result.append({
                "id": ann.id,
                "title": ann.title,
                "content": ann.content,
                "images": ann.images,
                "video": ann.video,
                "is_published": ann.is_published,
                "created_at": ann.created_at.isoformat(),
                "scheduled_time": ann.scheduled_time.isoformat() if ann.scheduled_time else None,
                "likes_count": len(ann.likes),
                "liked_by_user": liked_by_user,
                "comments": comment_list,
                "poll": {
                    "question": ann.poll_question,
                    "options": [
                        {"text": ann.poll_option_1, "votes": ann.votes_option_1},
                        {"text": ann.poll_option_2, "votes": ann.votes_option_2},
                        {"text": ann.poll_option_3, "votes": ann.votes_option_3},
                        {"text": ann.poll_option_4, "votes": ann.votes_option_4}
                    ] if ann.poll_question else None
                }
            })

        return jsonify({
            "status": "success",
            "announcements": result
        }), 200

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": "Internal Server Error",
            "error": str(e)
        }), 500


@user.route('/announcement/<int:announcement_id>', methods=['POST'])
def interact_with_announcement(announcement_id):
    try:
        userID = g.user.get('userID') if g.user else None
        if not userID:
            return jsonify({"status": "error", "message": "Unauthorized"}), 401

        user = User.query.filter_by(id=userID).first()
        if not user:
            return jsonify({"status": "error", "message": "No user found"}), 404

        data = request.get_json() or {}
        like = data.get('like')
        comment_text = data.get('comment', '').strip()

        announcement = Announcement.query.get(announcement_id)
        if not announcement:
            return jsonify({"status": "error", "message": "Announcement not found"}), 404

        response = {"status": "success", "message": []}

        if like is not None:
            existing_like = Likes.query.filter_by(announcement_id=announcement_id, empId=user.empId).first()
            if like:
                if not existing_like:
                    db.session.add(Likes(announcement_id=announcement_id, empId=user.empId))
                    response["message"].append("liked")
                else:
                    response["message"].append("You have already liked this.")
            else:
                if existing_like:
                    db.session.delete(existing_like)
                    response["message"].append("unliked")
                else:
                    response["message"].append("not_liked_yet")

        if comment_text:
            new_comment = Comments(
                announcement_id=announcement_id,
                empId=user.empId,
                comments=comment_text
            )
            db.session.add(new_comment)
            response["actions"].append("commented")

        db.session.commit()

        return jsonify(response), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({
            "status": "error",
            "message": "Internal Server Error",
            "error": str(e)
        }), 500


# ====================================
#        USER NOTICE SECTION
# ====================================


@user.route('/notice', methods=['GET'])
def get_Notice():
    try:
        userID = g.user.get('userID') if g.user else None
        if not userID:
            return jsonify({
                "status": "error",
                "message": "Unauthorized",
            }), 404

        user = User.query.filter_by(id=userID).first()
        if not user:
            return jsonify({
                "status": "error",
                "message": "User not found",
            }), 404

        userAdmin = SuperAdmin.query.filter_by(superId=user.superadminId).first()
        if not userAdmin:
            return jsonify({
                "status": "error",
                "message": "Unauthorized access",
            }), 403

        page = request.args.get('page', 1, type=int)
        limit = request.args.get('limit', 10, type=int)

        query = Notice.query.filter_by(superpanel=userAdmin.superadminPanel.id)
        pagination = query.order_by(Notice.createdAt.desc()).paginate(page=page, per_page=limit, error_out=False)

        notice_list = [{
            "id": n.id,
            "notice": n.notice,
            "createdAt": n.createdAt.isoformat() if n.createdAt else None
        } for n in pagination.items]

        return jsonify({
            "status": "success",
            "notices": notice_list,
            "pagination": {
                "page": pagination.page,
                "per_page": pagination.per_page,
                "total_pages": pagination.pages,
                "total_items": pagination.total
            }
        }), 200

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": "Internal Server Error",
            "error": str(e)
        }), 500


# ====================================
#        USER ASSETS SECTION
# ====================================

@user.route('/assets', methods=['POST'])
def request_assets():
    try:
        userId = g.user.get('userID') if g.user else None
        if not userId:
            return jsonify({
                "status": "error",
                "message": "Unauthorized",
            }), 404

        user = User.query.filter_by(id=userId).first()
        if not user:
            return jsonify({
                "status": "error",
                "message": "Unauthorized",
            }), 404

        data = request.get_json()
        required_fields = [ 'productName', 'qty', 'dateofrequest']

        for field in required_fields:
            if field not in data:
                return jsonify({
                    "status": "error",
                    "message": f"Missing required field: {field}"
                }), 400

        asset = ProductAsset(
            superpanel=user.panelData.id,
            productId=data['productId'],
            productName=data['productName'],
            category=data['category'],
            qty=data.get('qty', 1),
            department=user.department,
            purchaseDate=datetime.strptime(data['purchaseDate'], '%Y-%m-%d'),
            dateofrequest=datetime.strptime(data['dateofrequest'], '%Y-%m-%d'),
            warrantyTill=datetime.strptime(data['warrantyTill'], '%Y-%m-%d') if data.get('warrantyTill') else None,
            condition=data['condition'],
            status='pending',
            location=data['location'],
            assignedTo=str(user.empId)
        )

        db.session.add(asset)
        db.session.commit()

        return jsonify({
            "status": "success",
            "message": "Asset request submitted successfully",
            "data": {
                "asset_id": asset.id
            }
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({
            "status": "error",
            "message": "Internal Server Error",
            "error": str(e),
        }), 500


@user.route('/assets', methods=['GET'])
def get_assets():
    try:
        userId = g.user.get('userId') if g.user else None
        if not userId:
            return jsonify({
                "status": "error",
                "message": "Unauthorized"
            }), 404

        user = User.query.filter_by(id=userId).first()
        if not user or not user.panelData:
            return jsonify({
                "status": "error",
                "message": "Unauthorized",
            }), 400

        page = request.args.get('page', 1, type=int)
        limit = request.args.get('limit', 10, type=int)
        status_filter = request.args.get('status')

        tickets_query = user.panelData.MyAssets
        if not tickets_query:
            return jsonify({
                "status" : "error",
                "message" : "No Tickets yet.",
            }), 200

        tickets = [t for t in tickets_query if str(t.assignedTo) == str(userId)]

        if status_filter:
            tickets = [t for t in tickets if t.status == status_filter]

        total = len(tickets)

        start = (page - 1) * limit
        end = start + limit
        paginated_tickets = tickets[start:end]

        asset_list = []
        for asset in paginated_tickets:
            asset_list.append({
                "id": asset.id,
                "productId": asset.productId,
                "productName": asset.productName,
                "qty": asset.qty,
                "dateofrequest": asset.dateofrequest.strftime('%Y-%m-%d %H:%M:%S'),
                "department": asset.department,
                "status": asset.status,
            })

        return jsonify({
            "status": "success",
            "data": asset_list,
            "page": page,
            "total_pages": (total + limit - 1) // limit,
            "total_assets": total
        }), 200

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": "Internal Server Error",
            "error": str(e)
        }), 500
