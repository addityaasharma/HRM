from models import SuperAdmin, SuperAdminPanel, db, PunchData, User, UserTicket, AdminLeave, AdminDoc, Announcement, PollOption, AdminLeave, BonusPolicy, UserLeave, UserPanelData
from werkzeug.security import generate_password_hash, check_password_hash
from flask import Blueprint, request, jsonify, g
from middleware import create_tokens
from datetime import datetime, date
from config import cloudinary
from sqlalchemy import desc
from dateutil import parser
import cloudinary.uploader
from datetime import datetime
import random
import string
import re
import math


superAdminBP = Blueprint('superadmin',__name__, url_prefix='/superadmin')

def generate_super_id_from_last(last_super_id):
    if last_super_id:
        match = re.search(r'[A-Z]{4}(\d{4})[A-Z]{2}\d', last_super_id)
        if match:
            num_part = int(match.group(1))
        else:
            num_part = 1
    else:
        num_part = 1

    next_num = num_part + 1
    prefix = ''.join(random.choices(string.ascii_uppercase, k=4))
    middle = f"{next_num:04d}"
    suffix = ''.join(random.choices(string.ascii_uppercase, k=2)) + random.choice(string.digits)
    return prefix + middle + suffix

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


# ====================================
#         SUPERADMIN SECTION          
# ==================================== 

@superAdminBP.route('/signup', methods=['POST'])
def supAdmin_signup():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'message': 'Invalid or missing JSON body'}), 400

        required_fields = ['companyName', 'companyEmail', 'company_password', 'is_super_admin']
        if not all(field in data for field in required_fields):
            return jsonify({'message': 'All fields are required'}), 400

        if SuperAdmin.query.filter_by(companyEmail=data['companyEmail']).first():
            return jsonify({'message': 'User with this email already exists'}), 400

        last_admin = SuperAdmin.query.order_by(desc(SuperAdmin.id)).first()
        last_super_id = last_admin.superId if last_admin else None

        super_id = generate_super_id_from_last(last_super_id)

        newAdmin = SuperAdmin(
            superId=super_id,
            companyName=data.get('companyName'),
            companyEmail=data.get('companyEmail'),
            company_password=generate_password_hash(data.get('company_password')),
            is_super_admin=data.get('is_super_admin')
        )

        db.session.add(newAdmin)
        db.session.flush() 
        newAdmin.superadminPanel = SuperAdminPanel()
        db.session.commit()

        access_token, refresh_token = create_tokens(user_id=newAdmin.id, role='super_admin')

        return jsonify({
            'status': 'success',
            'message': 'User created successfully',
            'data': {
                'id': newAdmin.id,
                'superId': newAdmin.superId,
                'companyName': newAdmin.companyName,
                'companyEmail': newAdmin.companyEmail,
                'panelData': newAdmin.superadminPanel.id
            },
            'tokens': {
                'access_token': access_token,
                'refresh_token': refresh_token
            }
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({
            'status': 'error',
            'message': 'An error occurred during signup',
            'error': str(e)
        }), 500


@superAdminBP.route('/login', methods=['POST'])
def superadmin_login():
    data = request.get_json()
    required_fields = ['companyEmail', 'company_password']

    if not all(field in data for field in required_fields):
        return jsonify({
            'status': 'error',
            'message': 'All fields are required',
        }), 400

    exist_admin = SuperAdmin.query.filter_by(companyEmail=data['companyEmail']).first()

    if not exist_admin:
        return jsonify({
            'status': 'error',
            'message': 'No user found with this email',
        }), 404

    if not check_password_hash(exist_admin.company_password, data['company_password']):
        return jsonify({
            'status': 'error',
            'message': 'Incorrect password',
        }), 401

    panel = SuperAdminPanel.query.filter_by(id=exist_admin.superadminPanel.id).first()
    panel_data = {
        'id': panel.id,
        'alluser': [
            {
                'id': user.id,
                'userName': user.userName,
                'email': user.email,
                'empId': user.empId,
                'userRole': user.userRole,
            }
            for user in panel.allUsers
        ]
    } if panel else None

    access_token, refresh_token = create_tokens(user_id=exist_admin.id, role='super_admin')

    return jsonify({
        'status': 'success',
        'message': 'Login successful',
        'data': {
            'id': exist_admin.id,
            'superID': exist_admin.superId,
            'companyName': exist_admin.companyName,
            'companyEmail': exist_admin.companyEmail,
            'paneldata': panel_data,
            'is_super_admin': exist_admin.is_super_admin
        },
        'token': {
            'access_token': access_token,
            'refresh_token': refresh_token
        }
    }), 200


@superAdminBP.route('/mydetails', methods=['GET'])
def get_myDetails():
    try:
        userId = g.user.get('userID') if g.user else None
        if not userId:
            return jsonify({
                'status': 'error',
                'message': 'No auth token provided or user not found.'
            }), 400

        superadmin = SuperAdmin.query.filter_by(id=userId).first()
        if superadmin:
            adminDetails = {
                "id": superadmin.id,
                "companyName": superadmin.companyName,
                "companyEmail": superadmin.companyEmail,
            }
            return jsonify({"status": "success", "message": "Fetched Successfully", "data": adminDetails}), 200

        user = User.query.filter_by(id=userId).first()
        if not user:
            return jsonify({"status": "error", "message": "No user found"}), 404

        userDetails = {
            "id": user.id,
            "profileImage": user.profileImage,
            "userName": user.userName,
            "empId": user.empId,
            "email": user.email,
            "gender": user.gender,
            "number": user.number,
            "currentAddress": user.currentAddress,
            "permanentAddress": user.permanentAddress,
            "postal": user.postal,
            "city": user.city,
            "state": user.state,
            "country": user.country,
            "nationality": user.nationality,
            "panNumber": user.panNumber,
            "adharNumber": user.adharNumber,
            "uanNumber": user.uanNumber,
            "department": user.department,
            "onBoardingStatus": user.onBoardingStatus,
            "sourceOfHire": user.sourceOfHire,
            "currentSalary": user.currentSalary,
            "joiningDate": user.joiningDate.strftime('%Y-%m-%d') if user.joiningDate else None,
            "schoolName": user.schoolName,
            "degree": user.degree,
            "fieldOfStudy": user.fieldOfStudy,
            "dateOfCompletion": user.dateOfCompletion.strftime('%Y-%m-%d') if user.dateOfCompletion else None,
            "skills": user.skills,
            "occupation": user.occupation,
            "company": user.company,
            "experience": user.experience,
            "duration": user.duration,
            "userRole": user.userRole,
            "created_at": user.created_at.strftime('%Y-%m-%d %H:%M:%S') if user.created_at else None
        }

        return jsonify({"status": "success", "message": "Fetched Successfully", "data": userDetails}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({
            'status': 'error',
            'message': 'Internal server error',
            'error': str(e),
        }), 500


# ====================================
#            PUNCH SECTION            
# ====================================


@superAdminBP.route('/all-punchdetails', methods=['GET'])
def all_punchDetails():
    try:
        userId = g.user.get('userID') if g.user else None
        if not userId:
            return jsonify({
                'status': 'error',
                'message': 'No auth token provided or user not found.'
            }), 400

        superadmin = SuperAdmin.query.filter_by(id=userId).first()
        if not superadmin or not superadmin.superadminPanel:
            return jsonify({
                'status': 'error',
                'message': 'SuperAdmin or their panel not found.'
            }), 404

        if not superadmin.is_super_admin:
            user = User.query.filter_by(id=userId).first()
            if not user or user.userRole.lower() != 'hr':
                return jsonify({
                    'status': 'error',
                    'message': 'You are not allowed to access this route'
                }), 403

        users = User.query.filter_by(superadmin_panel_id=superadmin.superadminPanel.id).all()
        if not users:
            return jsonify({
                'status': 'error',
                'message': 'No users found under this SuperAdminPanel.'
            }), 404

        panel_ids = [user.panelData.id for user in users if user.panelData]
        if not panel_ids:
            return jsonify({
                'status': 'error',
                'message': 'No panel data found for users under this SuperAdmin.'
            }), 404

        query = PunchData.query.filter(PunchData.panelData.in_(panel_ids))

        # === Optional Date Filter ===
        date_str = request.args.get('date')
        if date_str:
            try:
                date_filter = datetime.strptime(date_str, "%Y-%m-%d").date()
                query = query.filter(db.func.date(PunchData.login) == date_filter)
            except ValueError:
                return jsonify({
                    'status': 'error',
                    'message': 'Invalid date format. Use YYYY-MM-DD.'
                }), 400

        department = request.args.get('department')
        if department:
            user_ids_in_dept = [user.panelData.id for user in users if user.department and user.department.lower() == department.lower()]
            query = query.filter(PunchData.user_panel_id.in_(user_ids_in_dept))

        status = request.args.get('status')
        if status:
            query = query.filter(PunchData.status.ilike(f"%{status}%"))

        search = request.args.get('query')
        if search:
            query = query.filter(
                db.or_(
                    PunchData.name.ilike(f'%{search}%'),
                    PunchData.email.ilike(f'%{search}%'),
                    PunchData.empId.ilike(f'%{search}%')
                )
            )

        # === Pagination ===
        page = request.args.get('page', default=1, type=int)
        limit = request.args.get('limit', default=10, type=int)
        paginated_data = query.order_by(PunchData.login.desc()).paginate(page=page, per_page=limit, error_out=False)

        # === Serialize ===
        punch_list = []
        for punch in paginated_data.items:
            punch_list.append({
                'id': punch.id,
                'empId': punch.empId,
                'name': punch.name,
                'email': punch.email,
                'login': punch.login.isoformat() if punch.login else None,
                'logout': punch.logout.isoformat() if punch.logout else None,
                'location': punch.location,
                'status': punch.status
            })

        return jsonify({
            'status': 'success',
            'message': 'Punch data fetched successfully.',
            'page': page,
            'limit': limit,
            'total': paginated_data.total,
            'total_pages': paginated_data.pages,
            'data': punch_list
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({
            'status': 'error',
            'message': 'Internal server error',
            'error': str(e),
        }), 500


@superAdminBP.route('/all-punchdetails/<int:punchId>',methods=['PUT'])
def editPunchDetails(punchId):
    data=request.get_json()

    required_feilds = ['status']
    if not all(field in data for field in required_feilds):
        return jsonify({
            "status"  : "error",
            "message" : "Status is required"
        })
    
    try:
        userID = g.user.get('userID') if g.user else None
        if not userID:
            return jsonify({
                'status' : "error",
                "message" : "No userid or auth token provided"
            }), 404
        
        superadmin = SuperAdmin.query.filter_by(id=userID).first()
        if not superadmin:
            user = User.query.filter_by(id=userID).first()
            if not user or user.userRole.lower() != "hr":
                return jsonify({
                    "status": "error",
                    "message": "You are not allowed to edit this role"
                }), 409
        
        punchdata = PunchData.query.filter_by(id=punchId).first()
        if not punchdata:
            return jsonify({
                "status" : "error",
                "message" : "No punch details found with this ID"
            }), 404
        
        punchdata.status = data['status']
        db.session.commit()

        return jsonify({
            "status" : "success",
            "message" : "Updated successfully"
        }), 200 
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            "status" : "error",
            "message" : "Internal Server Error",
            "error" : str(e)
        }),500


# ====================================
#         ALL EMPLOYEE SECTION        
# ====================================


@superAdminBP.route('/all-users/<int:id>', methods=['GET'])
def all_users_or_one(id):
    try:
        userID = g.user.get('userID') if g.user else None
        if not userID:
            return jsonify({'status': 'error', 'message': 'No auth or user found'}), 400

        superadmin = SuperAdmin.query.filter_by(id=userID).first()
        if not superadmin:
            return jsonify({'status': 'error', 'message': 'No admin found with this id'}), 400

        if not superadmin.is_super_admin:
            user = User.query.filter_by(id=userID).first()
            if not user or user.userRole.lower() != 'hr':
                return jsonify({'status': 'error', 'message': 'Unauthorized'}), 403

        superadminpanel = superadmin.superadminPanel
        if not superadminpanel:
            return jsonify({'status': 'error', 'message': 'No admin panel found with this user'}), 400

        all_users_query = superadminpanel.allUsers

        if id != 0:
            single_user = next((u for u in all_users_query if u.id == id), None)
            if not single_user:
                return jsonify({'status': 'error', 'message': 'User not found'}), 404

            user_data = {
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
                'occupation': user.occupation,
                'company': user.company,
                'experience': user.experience,
                'duration': user.duration,
                'userRole': user.userRole,
                'managerId': user.managerId,
                'superadmin_panel_id': user.superadmin_panel_id,
                'created_at': user.created_at.strftime("%Y-%m-%d %H:%M:%S") if user.created_at else None
            }

            return jsonify({'status': 'success', 'user': user_data}), 200

        department = request.args.get('department')
        if department:
            all_users_query = [user for user in all_users_query if user.department and user.department.lower() == department.lower()]

        search_query = request.args.get('query')
        if search_query:
            all_users_query = [user for user in all_users_query if search_query.lower() in user.userName.lower()]

        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 10))
        start = (page - 1) * limit
        end = start + limit
        total_users = len(all_users_query)
        paginated_users = all_users_query[start:end]

        user_list = [
            {
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
                'occupation': user.occupation,
                'company': user.company,
                'experience': user.experience,
                'duration': user.duration,
                'userRole': user.userRole,
                'managerId': user.managerId,
                'superadmin_panel_id': user.superadmin_panel_id,
                'created_at': user.created_at.strftime("%Y-%m-%d %H:%M:%S") if user.created_at else None
            }
            for user in paginated_users
        ]

        return jsonify({
            'status': 'success',
            'page': page,
            'limit': limit,
            'total_users': total_users,
            'total_pages': (total_users + limit - 1) // limit,
            'users': user_list
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': 'Internal server error', 'error': str(e)}), 500


@superAdminBP.route('/all-users/<int:userId>', methods=['PUT'])
def edit_user(userId):
    data = request.form
    if not data:
        return jsonify({
            "status": "error",
            "message": "Please provide data"
        }), 400

    try:
        auth_user_id = g.user.get('userID') if g.user else None
        if not auth_user_id:
            return jsonify({
                "status": "error",
                "message": "No auth token or user ID found"
            }), 401

        # Authorization check
        superadmin = SuperAdmin.query.filter_by(id=auth_user_id).first()
        if not superadmin:
            requesting_user = User.query.filter_by(id=auth_user_id).first()
            if not requesting_user or requesting_user.userRole.lower() != 'hr':
                return jsonify({
                    "status": "error",
                    "message": "Not authorized to update users"
                }), 403

        # Get the user to update
        user = User.query.filter_by(id=userId).first()
        if not user:
            return jsonify({
                "status": "error",
                "message": "User not found"
            }), 404

        # Define fields
        updatable_fields = [
            'profileImage', 'userName', 'gender', 'number', 'userRole',
            'currentAddress', 'permanentAddress', 'postal', 'city',
            'state', 'country', 'nationality', 'panNumber', 'adharNumber',
            'uanNumber', 'department', 'onBoardingStatus', 'sourceOfHire',
            'currentSalary', 'joiningDate', 'schoolName', 'degree',
            'fieldOfStudy', 'dateOfCompletion', 'skills', 'occupation',
            'company', 'experience', 'duration'
        ]

        # Field type groups
        integer_fields = ['currentSalary', 'experience']
        date_fields = ['dateOfCompletion']
        datetime_fields = ['joiningDate']
        string_fields = [
            'profileImage', 'userName', 'gender', 'number', 'currentAddress', 
            'permanentAddress', 'postal', 'city', 'state', 'country', 'nationality',
            'panNumber', 'adharNumber', 'uanNumber', 'department', 'onBoardingStatus',
            'sourceOfHire', 'schoolName', 'degree', 'fieldOfStudy', 'occupation',
            'company', 'duration', 'userRole'
        ]
        text_fields = ['skills']

        for field in updatable_fields:
            if field in data:
                value = data[field]

                # Handle empty string as None
                if value == '':
                    setattr(user, field, None)
                    continue

                if field in datetime_fields:
                    try:
                        setattr(user, field, date.fromisoformat(value))
                    except ValueError:
                        return jsonify({
                            'status': 'error',
                            'message': f'Invalid datetime format for {field}. Use YYYY-MM-DD or full ISO format.'
                        }), 400

                elif field in date_fields:
                    try:
                        setattr(user, field, date.fromisoformat(value))
                    except ValueError:
                        return jsonify({
                            'status': 'error',
                            'message': f'Invalid date format for {field}. Use YYYY-MM-DD.'
                        }), 400

                elif field in integer_fields:
                    try:
                        setattr(user, field, int(value))
                    except ValueError:
                        return jsonify({
                            'status': 'error',
                            'message': f'{field} must be a valid integer.'
                        }), 400

                elif field in string_fields or field in text_fields:
                    setattr(user, field, value)

        db.session.commit()

        return jsonify({
            "status": "success",
            "message": "User updated successfully"
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({
            "status": "error",
            "message": "Internal server error",
            "error": str(e)
        }), 500

@superAdminBP.route('/all-users', methods=['POST'])
def employeeCreation():
    data = request.form

    required_fields = ['userName', 'email', 'password', 'userRole']
    if not all(field in data for field in required_fields):
        return jsonify({'error': 'Missing required fields'}), 400

    email = data.get('email')

    if User.query.filter_by(email=email).first():
        return jsonify({'error': 'User already exists'}), 409

    try:
        userID = g.user.get('userID') if g.user else None
        if not userID:
            return jsonify({"status": "error", "message": "No user or auth token"}), 400

        superadmin = SuperAdmin.query.filter_by(id=userID).first()
        if superadmin:
            panel_id = superadmin.superadminPanel.id
            super_id = superadmin.superId
            superadminID = super_id  # ✅ Assign superadminID
        else:
            user = User.query.filter_by(id=userID).first()
            if not user or user.userRole.lower() != 'hr':
                return jsonify({"status": "error", "message": "You are not allowed to manage this"}), 403
            superadminID = user.superadminId

        superadminPanel = SuperAdmin.query.filter_by(superId=superadminID).first()
        if not superadminPanel:
            return jsonify({"status": "error", "message": "No admin found"}), 404

        newUser = User(
            superadminId=superadminID,
            userName=data.get('userName'),
            email=data.get('email'),
            password=generate_password_hash(data.get('password')),
            userRole=data.get('userRole'),
            gender=data.get('gender'),
            empId=gen_empId(),
            superadmin_panel_id=panel_id if superadmin else superadminPanel.id,
        )

        db.session.add(newUser)
        db.session.commit()

        return jsonify({"status": "success", "message": "Added Successfully"}), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": "Internal Server Error", "error": str(e)}), 500


@superAdminBP.route('/all-users/<int:id>', methods=['DELETE'])
def editEmployee(id):
    try:
        userID = g.user.get('userID') if g.user else None
        if not userID:
            return jsonify({"status" :"error" , "message" : "No user or auth token"}), 400
        
        superadmin = SuperAdmin.query.filter_by(id=userID).first()
        if superadmin:
            super_id = superadmin.superId
        else:
            user = User.query.filter_by(id=userID).first()
            if not user or user.userRole.lower() != 'hr':
                return jsonify({"status": "error", "message": "You are not allowed to manage this"}), 403
            
        user = User.query.filter_by(id=id).first()
        if not user:
            return jsonify({"status" : "error", "message" : "No user found"}),409
        
        db.session.delete(user)
        db.session.commit()
        
        return jsonify({"status" : "success", "message" : "Deleted successfully"}),200
            
    except Exception as e:
        db.session.rollback()
        return jsonify({"status" : "error", "message" : "Internal Server Error", "error" : str(e)})


# ====================================
#         USER TICKET SECTION         
# ====================================


@superAdminBP.route('/getTickets', methods=['GET'])
def allTickets():
    try:
        userId = g.user.get('userID') if g.user else None
        if not userId:
            return jsonify({
                'status': 'error',
                'message': "No user or auth token found."
            })

        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        
        department_filter = request.args.get('department', '').strip()
        status_filter = request.args.get('status', '').strip()
        priority_filter = request.args.get('priority', '').strip()
        
        if page < 1:
            page = 1
        if per_page < 1 or per_page > 100: 
            per_page = 10

        superadmin = SuperAdmin.query.filter_by(id=userId).first()
        if not superadmin or not superadmin.superadminPanel:
            return jsonify({
                'status': 'error',
                'message': 'SuperAdmin or their panel not found.'
            }), 404

        if not superadmin.is_super_admin:
            user = User.query.filter_by(id=userId).first()
            if not user or user.userRole.lower() != 'hr':
                return jsonify({
                    'status': 'error',
                    'message': 'You are not allowed to access this route'
                }), 403

        users = superadmin.superadminPanel.allUsers
        if not users:
            return jsonify({
                'status': 'error',
                'message': 'No users found under this SuperAdminPanel.'
            }), 404

        all_tickets = []
        for user in users:
            if user.panelData and user.panelData.UserTicket:
                for ticket in user.panelData.UserTicket:
                    if department_filter and ticket.department and ticket.department.lower() != department_filter.lower():
                        continue
                    if status_filter and ticket.status and ticket.status.lower() != status_filter.lower():
                        continue
                    if priority_filter and ticket.priority and ticket.priority.lower() != priority_filter.lower():
                        continue
                    
                    ticket_data = {
                        'ticket_id': ticket.id,
                        'user_name': ticket.userName,
                        'user_id': ticket.userId,
                        'emp_id': user.empId,
                        'date': ticket.date.isoformat() if ticket.date else None,
                        'topic': ticket.topic,
                        'problem': ticket.problem,
                        'priority': ticket.priority,
                        'department': ticket.department,
                        'document': ticket.document,
                        'status': ticket.status,
                        'user_email': user.email
                    }
                    all_tickets.append(ticket_data)

        all_tickets.sort(key=lambda x: x['date'] if x['date'] else '', reverse=True)
        
        total_tickets = len(all_tickets)
        total_pages = math.ceil(total_tickets / per_page) if total_tickets > 0 else 1
        
        start_index = (page - 1) * per_page
        end_index = start_index + per_page
        paginated_tickets = all_tickets[start_index:end_index]
        
        unique_departments = list(set([ticket['department'] for ticket in all_tickets if ticket['department']]))
        unique_statuses = list(set([ticket['status'] for ticket in all_tickets if ticket['status']]))
        unique_priorities = list(set([ticket['priority'] for ticket in all_tickets if ticket['priority']]))

        return jsonify({
            'status': 'success',
            'company_name': superadmin.companyName,
            'pagination': {
                'current_page': page,
                'per_page': per_page,
                'total_tickets': total_tickets,
                'total_pages': total_pages,
                'has_next': page < total_pages,
                'has_prev': page > 1,
                'next_page': page + 1 if page < total_pages else None,
                'prev_page': page - 1 if page > 1 else None
            },
            'filters': {
                'applied': {
                    'department': department_filter if department_filter else None,
                    'status': status_filter if status_filter else None,
                    'priority': priority_filter if priority_filter else None
                },
                'available': {
                    'departments': sorted(unique_departments),
                    'statuses': sorted(unique_statuses),
                    'priorities': sorted(unique_priorities)
                }
            },
            'tickets': paginated_tickets
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({
            'status': 'error',
            'message': 'Internal Server Error',
            'error': str(e)
        }), 500


@superAdminBP.route('/edit-ticket/<int:ticket_id>', methods=['PUT'])
def editTicket(ticket_id):
    data = request.get_json()
    if not data:
        return jsonify({
            'status': "error",
            'message': "No data provided",
        }), 400

    required_fields = ['status']
    if not all(field in data for field in required_fields):
        return jsonify({
            'status': 'error',
            'message': 'All fields (status, userID, ticket_id) are required.'
        }), 400

    try:
        userID = g.user.get('userID') if g.user else None
        if not userID:
            return jsonify({
                'status': 'error',
                'message': 'No auth or user found'
            }), 400

        superadmin = SuperAdmin.query.filter_by(id=userID).first()
        if not superadmin:
            return jsonify({
                'status': 'error',
                'message': 'No superadmin found with this id'
            }), 400

        if not superadmin.is_super_admin:
            user = User.query.filter_by(id=userID).first()
            if not user or user.userRole.lower() != 'hr':
                return jsonify({
                    'status': 'error',
                    'message': 'Unauthorized: You do not have access to this route'
                }), 403

        ticket = UserTicket.query.filter_by(id=ticket_id).first()
        if not ticket:
            return jsonify({
                'status': 'error',
                'message': 'Ticket not found.'
            }), 404

        ticket.status = data['status']

        db.session.commit()

        return jsonify({
            'status': 'success',
            'message': 'Ticket updated successfully',
            'ticket_id': ticket.id,
            'new_status': ticket.status
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({
            'status': "error",
            'message': "Internal Server Error",
            'error': str(e)
        }), 500


# ====================================
#     USER LEAVE CONTROL SECTION         
# ====================================


@superAdminBP.route('/userleave', methods=['GET'])
def user_leaves():
    try:
        userID = g.user.get('userID') if g.user else None
        if not userID:
            return jsonify({
                "status": "error",
                "message": "No auth token"
            }), 404

        # Pagination and filters
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        status_filter = request.args.get('status', '').strip().lower()
        department_filter = request.args.get('department', '').strip().lower()

        if page < 1:
            page = 1
        if per_page < 1 or per_page > 100:
            per_page = 10

        superadmin = SuperAdmin.query.filter_by(id=userID).first()
        panel_users = None

        if superadmin:
            panel_users = superadmin.superadminPanel.allUsers
        else:
            user = User.query.filter_by(id=userID).first()
            if not user or user.userRole.lower() != 'hr':
                return jsonify({
                    "status": "error",
                    "message": "You are not authorized"
                }), 403

            if not user.superadminId:
                return jsonify({
                    "status": "error",
                    "message": "No superadmin assigned to HR"
                }), 404

            assigned_admin = SuperAdmin.query.filter_by(superId=user.superadminId).first()
            if not assigned_admin or not assigned_admin.superadminPanel:
                return jsonify({
                    "status": "error",
                    "message": "No superadmin panel found"
                }), 404

            panel_users = assigned_admin.superadminPanel.allUsers

        if not panel_users:
            return jsonify({
                "status": "error",
                "message": "No users found in panel"
            }), 404

        all_leaves = []
        for user in panel_users:
            if not user.panelData:
                continue

            for leave in user.panelData.userLeaveData:
                # Apply filters before appending
                if status_filter and leave.status and leave.status.lower() != status_filter:
                    continue
                if department_filter and user.department and user.department.lower() != department_filter:
                    continue

                all_leaves.append({
                    "userId": user.id,
                    "userName": user.userName,
                    "leaveId" : leave.id,
                    "empId": leave.empId,
                    "department": user.department,
                    "leaveType": leave.leavetype,
                    "leaveFrom": leave.leavefrom.strftime('%Y-%m-%d') if leave.leavefrom else None,
                    "leaveTo": leave.leaveto.strftime('%Y-%m-%d') if leave.leaveto else None,
                    "status": leave.status,
                    "reason": leave.reason,
                    "days": leave.days,
                    "unpaidDays": leave.unpaidDays,
                    "appliedOnRaw": leave.createdAt,
                })

        if not all_leaves:
            return jsonify({
                "status": "error",
                "message": "No leave records found"
            }), 404

        # Sort by applied date descending
        all_leaves.sort(key=lambda x: x["appliedOnRaw"] or datetime.min, reverse=True)

        # Total and pagination logic
        total_leaves = len(all_leaves)
        total_pages = math.ceil(total_leaves / per_page)
        start_index = (page - 1) * per_page
        end_index = start_index + per_page
        paginated_leaves = all_leaves[start_index:end_index]

        # Format dates
        for leave in paginated_leaves:
            leave["appliedOn"] = leave["appliedOnRaw"].strftime('%Y-%m-%d') if leave["appliedOnRaw"] else None
            del leave["appliedOnRaw"]

        return jsonify({
            "status": "success",
            "message": "Leaves fetched successfully",
            "pagination": {
                "current_page": page,
                "per_page": per_page,
                "total_leaves": total_leaves,
                "total_pages": total_pages,
                "has_next": page < total_pages,
                "has_prev": page > 1,
                "next_page": page + 1 if page < total_pages else None,
                "prev_page": page - 1 if page > 1 else None
            },
            "filters_applied": {
                "status": status_filter or None,
                "department": department_filter or None
            },
            "data": paginated_leaves
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({
            "status": "error",
            "message": "Internal Server Error",
            "error": str(e)
        }), 500


@superAdminBP.route('/userleave/<int:leave_id>', methods=['PUT'])
def update_user_leave_status(leave_id):
    try:
        userID = g.user.get('userID') if g.user else None
        if not userID:
            return jsonify({
                "status": "error",
                "message": "No user ID or auth token provided"
            }), 404

        superadmin = SuperAdmin.query.filter_by(id=userID).first()

        if not superadmin:
            user = User.query.filter_by(id=userID).first()
            if not user or user.userRole.lower() != 'hr':
                return jsonify({
                    "status": "error",
                    "message": "You are not allowed to manage this."
                }), 403

        data = request.get_json()
        new_status = data.get('status')

        if not new_status or new_status.lower() not in ['pending', 'approved', 'rejected']:
            return jsonify({
                "status": "error",
                "message": "Invalid or missing status. Use: pending, approved, rejected."
            }), 400

        leave = UserLeave.query.get(leave_id)

        if not leave:
            return jsonify({
                "status": "error",
                "message": "Leave request not found"
            }), 404

        print(f"Old status: {leave.status}")
        
        # Update the status
        leave.status = new_status.lower()  # Ensure consistent case
        
        db.session.commit()
        db.session.refresh(leave)
        
        print(f"New status: {leave.status}, {leave.id}")

        return jsonify({
            "status": "success",
            "message": f"Leave status updated to '{leave.status}'",
            "leaveId": leave.id,
            "empId": leave.empId,
            "newStatus": leave.status
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({
            "status": "error",
            "message": "Internal Server Error",
            "error": str(e)
        }), 500
    


# ====================================
#        BONUS SECTION         
# ====================================


@superAdminBP.route('/bonus', methods=['GET'])
def get_bonus():
    try:
        userID = g.user.get('userID') if g.user else None
        if not userID:
            return jsonify({"status": "error", "message": "No user or auth token provided"}), 404

        superadmin = SuperAdmin.query.filter_by(id=userID).first()

        if superadmin:
            superpanelid = superadmin.superadminPanel.id
        else:
            user = User.query.filter_by(id=userID).first()
            if not user or user.userRole.lower() != 'hr':
                return jsonify({"status": "error", "message": "Unauthorized"}), 403

            userSuperAdmin = SuperAdmin.query.filter_by(superId=user.superadminId).first()
            if not userSuperAdmin:
                user = User.query.filter_by(id=userID).first()
                if not user or user.userRole.lower() != 'hr':
                    return jsonify({"status": "error", "message": "Unauthorized"}), 403

        bonus_policy  = userSuperAdmin.superadminPanel.adminBonusPolicy

        if not bonus_policy:
            return jsonify({
                "status": "error",
                "message": "No bonus policy found"
            }), 404

        return jsonify({
            "status": "success",
            "bonus_policy": {
                "id": bonus_policy.id,
                "bonus_name": bonus_policy.bonus_name,
                "bonus_description": bonus_policy.bonus_description,
                "bonus_methods": bonus_policy.bonus_methods,
                "amount": bonus_policy.amount
            }
        }), 200

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": "Internal Server Error",
            "error": str(e)
        }), 500


@superAdminBP.route('/bonus/<int:id>', methods=['PUT'])
def edit_bonus(id):
    data = request.get_json()
    if not data:
        return jsonify({
            "status": "error",
            "message": "No data provided"
        }), 400

    allowed_fields = ['bonus_name', 'bonus_description', 'bonus_methods', 'amount']
    if not any(field in data for field in allowed_fields):
        return jsonify({
            "status": "error",
            "message": "At least one field must be provided to update"
        }), 400

    try:
        userID = g.user.get('userID') if g.user else None
        if not userID:
            return jsonify({"status": "error", "message": "No user or auth token provided"}), 401

        superpanelid = None
        superadmin = SuperAdmin.query.filter_by(id=userID).first()

        if superadmin:
            superpanelid = superadmin.superadminPanel.id
        else:
            user = User.query.filter_by(id=userID).first()
            if not user or user.userRole.lower() != 'hr':
                return jsonify({"status": "error", "message": "Unauthorized"}), 403

            userSuperAdmin = SuperAdmin.query.filter_by(superId=user.superadminId).first()
            if not userSuperAdmin:
                return jsonify({"status": "error", "message": "Unauthorized"}), 403

            superpanelid = userSuperAdmin.superadminPanel.id

        bonuspolicy = BonusPolicy.query.filter_by(id=id, superPanelID=superpanelid).first()
        if not bonuspolicy:
            return jsonify({
                "status": "error",
                "message": "No bonus policy found"
            }), 404

        if 'bonus_name' in data:
            bonuspolicy.bonus_name = data['bonus_name']
        if 'bonus_description' in data:
            bonuspolicy.bonus_description = data['bonus_description']
        if 'bonus_methods' in data:
            bonuspolicy.bonus_methods = data['bonus_methods']
        if 'amount' in data:
            bonuspolicy.amount = int(data['amount'])

        db.session.commit()

        return jsonify({
            "status": "success",
            "message": "Updated successfully"
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({
            "status": "error",
            "message": "Internal Server Error",
            "error": str(e)
        }), 500


@superAdminBP.route('/bonus/<int:id>', methods=['DELETE'])
def delete_bonus(id):
    try:
        userID = g.user.get('userID') if g.user else None
        if not userID:
            return jsonify({
                "status": "error",
                "message": "No user or auth token provided"
            }), 401

        superpanelid = None
        superadmin = SuperAdmin.query.filter_by(id=userID).first()

        if superadmin:
            superpanelid = superadmin.superadminPanel.id
        else:
            user = User.query.filter_by(id=userID).first()
            if not user or user.userRole.lower() != 'hr':
                return jsonify({
                    "status": "error",
                    "message": "Unauthorized"
                }), 403

            userSuperAdmin = SuperAdmin.query.filter_by(superId=user.superadminId).first()
            if not userSuperAdmin:
                return jsonify({
                    "status": "error",
                    "message": "Unauthorized"
                }), 403

            superpanelid = userSuperAdmin.superadminPanel.id

        bonuspolicy = BonusPolicy.query.filter_by(id=id).first()
        if not bonuspolicy:
            return jsonify({
                "status": "error",
                "message": "No bonus policy found"
            }), 404

        db.session.delete(bonuspolicy)
        db.session.commit()

        return jsonify({
            "status": "success",
            "message": "Bonus policy deleted successfully"
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({
            "status": "error",
            "message": "Internal Server Error",
            "error": str(e)
        }), 500


# ====================================
#      CODE OF CONDUCT SECTION               
# ====================================

@superAdminBP.route('/coc')
def add_codeOfConduct():
    try:
        userID = g.user.get('userID') if g.user else None
        if not userID:
            return jsonify({
                "status" : "error",
                "message" : "No user id or auth token found"
            }), 404

        superadmin = SuperAdmin.query.filter_by(id=userID).first()
        if not superadmin:
            user = User.query.filter_by(id=userID).first()
            if not user or user.userRole.lower() != 'hr':
                return jsonify({
                    "status" : "error",
                    "message" : "Unauthorized"
                }), 404
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            "status" : "error",
            "message" : "Internal Server Error",
            "error" : str(e)
        }), 500