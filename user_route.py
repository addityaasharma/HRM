from models import User,UserPanelData,db,SuperAdmin,PunchData, UserTicket, UserDocument
from werkzeug.security import generate_password_hash, check_password_hash
from flask import Blueprint, request, json, jsonify, g
from otp_utils import generate_otp, send_otp
from middleware import create_tokens
from datetime import datetime,time
from dotenv import load_dotenv
from config import cloudinary
import cloudinary.uploader
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


@user.route('/punchin', methods=['POST'])
def punch_details():
    try:
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

        userId = g.user.get('userID') if g.user else None
        if not userId:
            return jsonify({
                'status': 'error',
                'message': 'User ID is missing or not authenticated'
            }), 400

        user = User.query.filter_by(id=userId).first()
        if not user:
            return jsonify({
                'status': 'error',
                'message': 'No user found with this ID'
            }), 404

        usersPanelData = user.panelData
        if not usersPanelData:
            return jsonify({
                'status': 'error',
                'message': 'No user panel data found'
            }), 404

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


@user.route('/punchin/<int:punchId>',methods=['PUT'])
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
        # Convert logout datetime (auto-parse Zulu/UTC format)
        logout_time = datetime.fromisoformat(data.get('logout').replace('Z', '+00:00'))

        # Convert totalHour string "HH:MM:SS" to time object
        total_hour_str = data.get('totalHour')
        try:
            h, m, s = map(int, total_hour_str.strip().split(':'))
            total_hour_time = time(hour=h, minute=m, second=s)
        except ValueError:
            return jsonify({
                "status": "error",
                "message": "Invalid format for totalHour. Expected HH:MM:SS"
            }), 400

        # Auth and user check
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

        # Update
        punchdata.logout = logout_time
        punchdata.location = data['location']
        punchdata.totalhour = total_hour_time
        punchdata.status = 'fullday'

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


@user.route('/raise_ticket', methods=['POST'])
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


@user.route('/get_ticket', methods=['GET'])
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
