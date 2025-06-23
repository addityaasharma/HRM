from models import SuperAdmin, SuperAdminPanel, db, PunchData, User, UserTicket, AdminLeave, AdminDoc, Announcement, AdminLeave, BonusPolicy, UserLeave, UserPanelData, ShiftTimeManagement, RemotePolicy, PayrollPolicy, Notice, TaskManagement, TaskUser, TaskComments, AdminDetail, Likes, AdminHoliday, ProductAsset, AdminDepartment, TicketAssignmentLog, UserAccess, UserPromotion, UserSalaryDetails, UserChat, AdminLocation
from werkzeug.security import generate_password_hash, check_password_hash
from flask import Blueprint, request, jsonify, g
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
from socket_instance import socketio
from middleware import create_tokens
from datetime import datetime, date
from config import cloudinary
import logging, calendar, os
from sqlalchemy import desc
from dateutil import parser
import cloudinary.uploader
from flask import url_for
import math, holidays
import re, json
import random 
import string


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


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

def get_authorized_superadmin(required_section=None, required_permissions=None):
    userID = g.user.get('userID') if g.user else None
    if not userID:
        return None, jsonify({"status": "error", "message": "No auth token"}), 401

    superadmin = SuperAdmin.query.filter_by(id=userID).first()
    if superadmin:
        return superadmin, None, None

    user = User.query.filter_by(id=userID).first()
    if not user:
        return None, jsonify({"status": "error", "message": "Unauthorized user"}), 403

    if required_section and required_permissions:
        if isinstance(required_permissions, str):
            required_permissions = [required_permissions]

        matched_permission = next((
            access for access in user.access_permissions
            if access.section == required_section.lower()
            and access.permission in [perm.lower() for perm in required_permissions]
            and access.allowed
        ), None)

        if not matched_permission:
            return None, jsonify({
                "status": "error",
                "message": f"Access denied for '{required_section}' section with required permission(s): {required_permissions}"
            }), 403

    superadmin = SuperAdmin.query.filter_by(superId=user.superadminId).first()
    if not superadmin:
        return None, jsonify({"status": "error", "message": "No superadmin found"}), 404

    return superadmin, None, None



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
            company_type=data.get('company_type'),
            company_website=data.get('company_website'),
            company_estabilish=data.get('company_estabilish'),
            company_years=data.get('company_years'),
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

    email = data['companyEmail']
    password = data['company_password']

    # Try SuperAdmin first
    exist_admin = SuperAdmin.query.filter_by(companyEmail=email).first()

    if exist_admin:
        if not check_password_hash(exist_admin.company_password, password):
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
            'message': 'Login successful (SuperAdmin)',
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


    user = User.query.filter_by(email=email).first()
    if user and not user.userRole.lower() == 'hr':
        if not check_password_hash(user.password, password):  # Assumes User model has `password` field
            return jsonify({
                'status': 'error',
                'message': 'Incorrect password',
            }), 401

        access_token, refresh_token = create_tokens(user_id=user.id, role='hr')

        return jsonify({
            'status': 'success',
            'message': 'Login successful (HR)',
            'data': {
                'id': user.id,
                'userName': user.userName,
                'email': user.email,
                'empId': user.empId,
                'userRole': user.userRole,
                'superadminId': user.superadminId
            },
            'token': {
                'access_token': access_token,
                'refresh_token': refresh_token
            }
        }), 200

    return jsonify({
        "status": "error",
        "message": "Unauthorized: Account not found or role not allowed",
    }), 404


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
            panel = superadmin.superadminPanel
            admin_detail = panel.adminDetails if panel else None

            adminDetails = {
                "id": superadmin.id,
                "companyName": superadmin.companyName,
                "companyEmail": superadmin.companyEmail,
                "company_type": superadmin.company_type,
                "company_website": superadmin.company_website,
                "company_estabilish": superadmin.company_estabilish.strftime('%Y-%m-%d') if superadmin.company_estabilish else None,
                "company_years": superadmin.company_years,
                "is_super_admin": superadmin.is_super_admin,
            }

            if admin_detail:
                adminDetails.update({
                    "legalName": admin_detail.legalCompanyName,
                    "panNumber": admin_detail.panNumber,
                    "cinNumber": admin_detail.cinNumber,
                    "udyamNumber": admin_detail.udyamNumber,
                    "gstNumber": admin_detail.gstNumber,
                    "officialmail": admin_detail.officialmail,
                    "phoneNumber": admin_detail.phoneNumber,
                    "linkedin": admin_detail.linkedin,
                    "twitter": admin_detail.twitter,
                    "ceo": admin_detail.ceo,
                    "cto": admin_detail.cto,
                    "hrmanager": admin_detail.hrmanager,
                    "headOffice" : admin_detail.headOffice,
                    "state" : admin_detail.state,
                    "zipCode" : admin_detail.zipCode,
                    "city" : admin_detail.city,
                    "country" : admin_detail.country,
                    "location" : admin_detail.location,
                })

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


@superAdminBP.route('/mydetails', methods=['PUT'])
def edit_myDetails():
    try:
        userId = g.user.get('userID') if g.user else None
        if not userId:
            return jsonify({"status": "error", "message": "Unauthorized"}), 401

        superadmin = SuperAdmin.query.filter_by(id=userId).first()
        if not superadmin:
            return jsonify({"status": "error", "message": "SuperAdmin not found"}), 404

        data = request.form.to_dict()
        
        if 'company_image' in request.files:
            image_file = request.files['company_image']
            if image_file:
                upload_result = cloudinary.uploader.upload(image_file)
                image_url = upload_result.get('secure_url')
                superadmin.company_image = image_url

        superadmin.companyName = data.get('companyName', superadmin.companyName)
        superadmin.companyEmail = data.get('companyEmail', superadmin.companyEmail)
        superadmin.company_type = data.get('company_type', superadmin.company_type)
        superadmin.company_website = data.get('company_website', superadmin.company_website)
        superadmin.company_years = data.get('company_years', superadmin.company_years)
        superadmin.is_super_admin = data.get('is_super_admin', superadmin.is_super_admin)

        estabilish = data.get('company_estabilish')
        if estabilish:
            try:
                superadmin.company_estabilish = datetime.strptime(estabilish, '%Y-%m-%d')
            except ValueError:
                return jsonify({"status": "error", "message": "Invalid date format. Use YYYY-MM-DD"}), 400

        panel = superadmin.superadminPanel
        if panel and panel.adminDetails:
            admin = panel.adminDetails
            admin.legalCompanyName = data.get('legalName', admin.legalCompanyName)
            admin.panNumber = data.get('panNumber', admin.panNumber)
            admin.cinNumber = data.get('cinNumber', admin.cinNumber)
            admin.udyamNumber = data.get('udyamNumber', admin.udyamNumber)
            admin.gstNumber = data.get('gstNumber', admin.gstNumber)
            admin.officialmail = data.get('officialmail', admin.officialmail)
            admin.phoneNumber = data.get('phoneNumber', admin.phoneNumber)
            admin.linkedin = data.get('linkedin', admin.linkedin)
            admin.twitter = data.get('twitter', admin.twitter)
            admin.ceo = data.get('ceo', admin.ceo)
            admin.cto = data.get('cto', admin.cto)
            admin.hrmanager = data.get('hrmanager', admin.hrmanager)
            admin.headOffice = data.get('headOffice', admin.headOffice)
            admin.state = data.get('state', admin.state)
            admin.zipCode = data.get('zipCode', admin.zipCode)
            admin.city = data.get('city', admin.city)
            admin.country = data.get('country', admin.country)
            admin.location = data.get('location', admin.location)

        db.session.commit()
        return jsonify({"status": "success", "message": "Details updated successfully"}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({
            "status": "error",
            "message": "Internal server error",
            "error": str(e)
        }), 500


@superAdminBP.route('/mydetails', methods=['POST'])
def create_company_details():
    try:
        superadmin, err, status = get_authorized_superadmin()
        if err:
            return err, status

        panel = superadmin.superadminPanel
        if not panel:
            return jsonify({
                "status": "error",
                "message": "SuperAdmin panel not found"
            }), 404

        if panel.adminDetails:
            return jsonify({
                "status": "error",
                "message": "AdminDetails already exist"
            }), 409

        data = request.get_json()
        if not data:
            return jsonify({
                "status": "error",
                "message": "No input data provided"
            }), 400

        details = AdminDetail(
            superpanel=panel.id,
            legalCompanyName=data.get('legalName'),
            panNumber=data.get('panNumber'),
            cinNumber=data.get('cinNumber'),
            udyamNumber=data.get('udyamNumber'),
            gstNumber=data.get('gstNumber'),
            officialmail=data.get('officialmail'),
            phoneNumber=data.get('phoneNumber'),
            linkedin=data.get('linkedin'),
            twitter=data.get('twitter'),
            ceo=data.get('ceo'),
            cto=data.get('cto'),
            hrmanager=data.get('hrmanager'),
            headOffice = data.get('headOffice'),
            state = data.get('state'),
            zipCode = data.get('zipCode'),
            city = data.get('city'),
            country = data.get('country'),
            location = data.get('location'),
        )

        db.session.add(details)
        db.session.commit()

        return jsonify({
            "status": "success",
            "message": "AdminDetails created successfully"
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({
            "status": "error",
            "message": "Internal Server Error",
            "error": str(e),
        }), 500


# ====================================
#            PUNCH SECTION  - Get all punch in details of the users and can also edit 
# ====================================


@superAdminBP.route('/punchdetails', methods=['GET'])
def all_punchDetails():
    try:
        superadmin, err, status = get_authorized_superadmin()
        if err:
            return err, status

        alluser = superadmin.superadminPanel.allUsers
        if not alluser:
            return jsonify({
                "status": "error",
                "message": "No users found under this panel",
            }), 404

        status_filter = request.args.get('status')
        department_filter = request.args.get('department')
        search_query = request.args.get('search', '').lower()
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 10))

        punchlist = []

        for user in alluser:
            panel_data = user.panelData
            if not panel_data:
                continue

            if department_filter and user.department.lower() != department_filter.lower():
                continue

            if search_query:
                if not (
                    search_query in (user.userName or "").lower() or
                    search_query in (user.email or "").lower() or
                    search_query in (user.empId or "").lower()
                ):
                    continue

            for punch in panel_data.userPunchData:
                if status_filter and punch.status.lower() != status_filter.lower():
                    continue

                punchlist.append({
                    "punch_id": punch.id,
                    "empId": punch.empId,
                    "name": punch.name,
                    "email": punch.email,
                    "login": punch.login.isoformat() if punch.login else None,
                    "logout": punch.logout.isoformat() if punch.logout else None,
                    "location": punch.location,
                    "image": punch.image,
                    "status": punch.status,
                    "totalhour": str(punch.totalhour) if punch.totalhour else None,
                    "productivehour": punch.productivehour.isoformat() if punch.productivehour else None,
                    "shift": punch.shift.isoformat() if punch.shift else None
                })

        # Apply pagination
        total = len(punchlist)
        start = (page - 1) * per_page
        end = start + per_page
        paginated_data = punchlist[start:end]

        return jsonify({
            'status': 'success',
            'message': 'Punch data fetched successfully.',
            'data': paginated_data,
            'meta': {
                'total': total,
                'page': page,
                'per_page': per_page,
                'pages': (total + per_page - 1) // per_page
            }
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({
            'status': 'error',
            'message': 'Internal server error',
            'error': str(e),
        }), 500


@superAdminBP.route('/punchdetails/<int:punchId>',methods=['PUT'])
def editPunchDetails(punchId):
    data=request.get_json()

    required_feilds = ['status']
    if not all(field in data for field in required_feilds):
        return jsonify({
            "status"  : "error",
            "message" : "Status is required"
        }), 404
    
    try:
        superadmin, err, status = get_authorized_superadmin()
        if err:
            return err, status
        
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
#         ALL EMPLOYEE SECTION  - Edit, Add or Delete All Employee 
# ====================================


@superAdminBP.route('/all-users/<int:id>', methods=['GET'])
def all_users_or_one(id):
    try:
        superadmin, err, status = get_authorized_superadmin()
        if err:
            return err, status

        superadminpanel = superadmin.superadminPanel
        if not superadminpanel:
            return jsonify({'status': 'error', 'message': 'No admin panel found with this user'}), 400

        all_users_query = superadminpanel.allUsers

        def get_user_access_list(user):
            return [{
                'section': access.section,
                'permission': access.permission,
                'allowed': access.allowed
            } for access in user.access_permissions]

        if id != 0:
            single_user = next((u for u in all_users_query if u.id == id), None)
            if not single_user:
                return jsonify({'status': 'error', 'message': 'User not found'}), 404

            user_promotions = []
            if single_user.panelData:
                user_promotions = [{
                    "id": promo.id,
                    "empId": promo.empId,
                    "new_designation": promo.new_designation,
                    "previous_department": promo.previous_department,
                    "new_department": promo.new_department,
                    "description": promo.description,
                    "dateofpromotion": promo.dateofpromotion.strftime("%Y-%m-%d") if promo.dateofpromotion else None
                } for promo in single_user.panelData.UserPromotion]

            user_data = {
                'id': single_user.id,
                'profileImage': single_user.profileImage,
                'superadminId': single_user.superadminId,
                'userName': single_user.userName,
                'empId': single_user.empId,
                'email': single_user.email,
                'gender': single_user.gender,
                'number': single_user.number,
                'currentAddress': single_user.currentAddress,
                'permanentAddress': single_user.permanentAddress,
                'postal': single_user.postal,
                'city': single_user.city,
                'state': single_user.state,
                'country': single_user.country,
                'birthday': single_user.birthday.strftime("%Y-%m-%d"),
                'nationality': single_user.nationality,
                'panNumber': single_user.panNumber,
                'adharNumber': single_user.adharNumber,
                'uanNumber': single_user.uanNumber,
                'department': single_user.department,
                'onBoardingStatus': single_user.onBoardingStatus,
                'sourceOfHire': single_user.sourceOfHire,
                'currentSalary': single_user.currentSalary,
                'joiningDate': single_user.joiningDate.strftime("%Y-%m-%d") if single_user.joiningDate else None,
                'schoolName': single_user.schoolName,
                'degree': single_user.degree,
                'fieldOfStudy': single_user.fieldOfStudy,
                'dateOfCompletion': single_user.dateOfCompletion.strftime("%Y-%m-%d") if single_user.dateOfCompletion else None,
                'skills': single_user.skills,
                'shift': single_user.shift,
                'occupation': single_user.occupation,
                'company': single_user.company,
                'experience': single_user.experience,
                'duration': single_user.duration,
                'userRole': single_user.userRole,
                'managerId': single_user.managerId,
                'superadmin_panel_id': single_user.superadmin_panel_id,
                'created_at': single_user.created_at.strftime("%Y-%m-%d %H:%M:%S") if single_user.created_at else None,
                'access': get_user_access_list(single_user),
                'promotions': user_promotions
            }

            return jsonify({'status': 'success', 'user': user_data}), 200

        department = request.args.get('department')
        if department and department.lower() != 'all':
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
                'birthday': user.birthday.strftime("%Y-%m-%d") if user.birthday else None,
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
                'created_at': user.created_at.strftime("%Y-%m-%d %H:%M:%S") if user.created_at else None,
                'access': get_user_access_list(user)
            }
            for user in paginated_users
        ]

        # total_users = len(all_users_query)
        male_count = sum(1 for user in all_users_query if user.gender and user.gender.lower() == "male")
        female_count = sum(1 for user in all_users_query if user.gender and user.gender.lower() == "female")

        return jsonify({
            'status': 'success',
            'page': page,
            'limit': limit,
            'total_users': total_users,
            'total_pages': (total_users + limit - 1) // limit,
            'users': user_list,
            'males': male_count,
            'females': female_count
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': 'Internal Server Error', 'error': str(e)}), 500


@superAdminBP.route('/all-users/<int:userId>', methods=['PUT'])
def edit_user(userId):
    data = request.form
    if not data:
        return jsonify({
            "status": "error",
            "message": "Please provide data"
        }), 400

    try:
        superadmin, err, status = get_authorized_superadmin()
        if err:
            return err, status

        user = User.query.filter_by(id=userId).first()
        if not user:
            return jsonify({
                "status": "error",
                "message": "User not found"
            }), 404

        updatable_fields = [
            'userName', 'gender', 'number', 'userRole',
            'currentAddress', 'permanentAddress', 'postal', 'city',
            'state', 'country', 'nationality', 'panNumber', 'adharNumber',
            'uanNumber', 'department', 'onBoardingStatus', 'sourceOfHire',
            'currentSalary', 'joiningDate', 'schoolName', 'degree',
            'fieldOfStudy', 'dateOfCompletion', 'skills', 'occupation',
            'company', 'experience', 'duration', 'shift', 'birthday'
        ]
        integer_fields = ['currentSalary', 'experience', 'number']
        date_fields = ['dateOfCompletion']
        datetime_fields = ['joiningDate', 'birthday']
        string_fields = [
            'profileImage', 'userName', 'gender', 'currentAddress',
            'permanentAddress', 'postal', 'city', 'state', 'country', 'nationality',
            'panNumber', 'adharNumber', 'uanNumber', 'department', 'onBoardingStatus',
            'sourceOfHire', 'schoolName', 'degree', 'fieldOfStudy', 'occupation',
            'company', 'duration', 'userRole', 'shift'
        ]
        text_fields = ['skills']

        updated_any = False

        for field in updatable_fields:
            if field in data:
                value = data[field]

                if value == '':
                    setattr(user, field, None)
                elif field in datetime_fields or field in date_fields:
                    try:
                        setattr(user, field, date.fromisoformat(value))
                    except ValueError:
                        return jsonify({'status': 'error', 'message': f'Invalid date format for {field}'}), 400
                elif field in integer_fields:
                    try:
                        setattr(user, field, int(value))
                    except ValueError:
                        return jsonify({'status': 'error', 'message': f'{field} must be a valid integer'}), 400
                else:
                    setattr(user, field, value)

                updated_any = True

        raw_access = data.get("access")
        if raw_access is not None:
            try:
                UserAccess.query.filter_by(user_id=user.id).delete()

                access_list = json.loads(raw_access)
                for access in access_list:
                    section = access.get("section")
                    permission = access.get("permission")
                    allowed = access.get("allowed", False)

                    if section and permission:
                        new_access = UserAccess(
                            user_id=user.id,
                            section=section.lower(),
                            permission=permission.lower(),
                            allowed=bool(allowed)
                        )
                        db.session.add(new_access)

                updated_any = True

            except Exception as access_error:
                db.session.rollback()
                return jsonify({
                    "status": "error",
                    "message": "Access update failed",
                    "error": str(access_error)
                }), 400

        if updated_any:
            db.session.commit()
            return jsonify({
                "status": "success",
                "message": "User and/or access updated successfully"
            }), 200
        else:
            return jsonify({
                "status": "info",
                "message": "No changes were made"
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
            superadminID = superadmin.superId
        else:
            user = User.query.filter_by(id=userID).first()
            if not user or user.userRole.lower() != 'hr':
                return jsonify({"status": "error", "message": "You are not allowed to manage this"}), 403
            superadminID = user.superadminId
            superadmin = SuperAdmin.query.filter_by(superId=superadminID).first()
            panel_id = user.superadmin_panel_id

        if not superadmin:
            return jsonify({"status": "error", "message": "No superadmin found"}), 404

        newUser = User(
            superadminId=superadminID,
            userName=data.get('userName'),
            email=data.get('email'),
            password=generate_password_hash(data.get('password')),
            userRole=data.get('userRole'),
            gender=data.get('gender'),
            empId=gen_empId(),
            superadmin_panel_id=panel_id,
        )

        db.session.add(newUser)
        db.session.commit()

        raw_access = data.get('access')
        if raw_access:
            try:
                access_list = json.loads(raw_access)
                for access in access_list:
                    section = access.get("section")
                    permission = access.get("permission")
                    allowed = access.get("allowed", False)

                    if section and permission:
                        new_access = UserAccess(
                            user_id=newUser.id,
                            section=section.lower(),
                            permission=permission.lower(),
                            allowed=bool(allowed)
                        )
                        db.session.add(new_access)
                db.session.commit()
            except Exception as access_error:
                db.session.rollback()
                return jsonify({
                    "status": "error",
                    "message": "User created, but access assignment failed",
                    "error": str(access_error)
                }), 207 

        return jsonify({"status": "success", "message": "User created successfully"}), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({
            "status": "error",
            "message": "Internal Server Error",
            "error": str(e)
        }), 500


@superAdminBP.route('/all-users/<int:id>', methods=['DELETE'])
def editEmployee(id):
    try:
        superadmin, err, status = get_authorized_superadmin()
        if err:
            return err, status
            
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
#         USER TICKET SECTION - get all tickets from the user side and update it.         
# ====================================


@superAdminBP.route('/ticket', methods=['GET'])
def allTickets():
    try:
        superadmin, err, status = get_authorized_superadmin()
        if err:
            return err, status

        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        
        department_filter = request.args.get('department', '').strip()
        status_filter = request.args.get('status', '').strip()
        priority_filter = request.args.get('priority', '').strip()

        if page < 1:
            page = 1
        if per_page < 1 or per_page > 100:
            per_page = 10

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

                    logs = [{
                        'assigned_by': log.assigned_by_empId,
                        'assigned_to': log.assigned_to_empId,
                        'assigned_at': log.assigned_at.isoformat() if log.assigned_at else None
                    } for log in ticket.assignment_logs]

                    ticket_data = {
                        'ticket_id': ticket.id,
                        'user_name': ticket.userName,
                        'user_id': ticket.userId,
                        'emp_id': user.empId,
                        'user_email': user.email,
                        'date': ticket.date.isoformat() if ticket.date else None,
                        'topic': ticket.topic,
                        'problem': ticket.problem,
                        'priority': ticket.priority,
                        'department': ticket.department,
                        'document': ticket.document,
                        'status': ticket.status,
                        'assigned_to_empId': ticket.assigned_to_empId,
                        'logs': logs
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


@superAdminBP.route('/ticket/<int:ticket_id>', methods=['PUT'])
def editTicket(ticket_id):
    data = request.get_json()
    if not data:
        return jsonify({
            'status': "error",
            'message': "No data provided",
        }), 400

    try:
        superadmin, err, status = get_authorized_superadmin(
            required_section="ticket",
            required_permissions="assign"
        )
        if err:
            return err, status

        userID = g.user.get('userID') if g.user else None
        if not userID:
            return jsonify({
                'status': 'error',
                'message': 'No auth or user found'
            }), 400

        ticket = UserTicket.query.filter_by(id=ticket_id).first()
        if not ticket:
            return jsonify({
                'status': 'error',
                'message': 'Ticket not found.'
            }), 404

        user = User.query.filter_by(id=userID).first()
        is_superadmin = superadmin.id == userID if superadmin else False

        # Track original assigned user
        old_assignee_empId = ticket.assigned_to_empId
        status_changed = False

        if 'status' in data and data['status'] != ticket.status:
            ticket.status = data['status']
            status_changed = True

        if 'problem' in data:
            ticket.problem = data['problem']

        if 'assign_to_empId' in data:
            new_assignee_empId = data['assign_to_empId']
            assigned_to_user = User.query.filter_by(empId=new_assignee_empId).first()
            if not assigned_to_user:
                return jsonify({'status': 'error', 'message': 'User with empId not found'}), 404

            if ticket.assigned_to_empId != new_assignee_empId:
                log = TicketAssignmentLog(
                    ticket_id=ticket.id,
                    assigned_by_empId=superadmin.companyEmail if is_superadmin else user.empId,
                    assigned_to_empId=new_assignee_empId
                )
                db.session.add(log)
                ticket.assigned_to_empId = new_assignee_empId

                socketio.emit(
                    'ticket_assigned',
                    {
                        'ticket_id': ticket.id,
                        'message': f"You have been assigned ticket #{ticket.id}"
                    },
                    room=new_assignee_empId
                )

        db.session.commit()

        if status_changed and ticket.assigned_to_empId:
            socketio.emit(
                'ticket_status_update',
                {
                    'ticket_id': ticket.id,
                    'new_status': ticket.status,
                    'message': f"Status of your ticket #{ticket.id} changed to '{ticket.status}'"
                },
                room=ticket.assigned_to_empId
            )

        return jsonify({
            'status': 'success',
            'message': 'Ticket updated successfully',
            'ticket_id': ticket.id,
            'new_status': ticket.status,
            'assigned_to': ticket.assigned_to_empId
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({
            'status': "error",
            'message': "Internal Server Error",
            'error': str(e)
        }), 500


@superAdminBP.route('/assigned-tickets', methods=['GET'])
def get_assigned_tickets():
    try:
        userId = g.user.get('userID') if g.user else None
        if not userId:
            return jsonify({
                'status': 'error',
                'message': 'No user or auth token found.'
            }), 401

        user = User.query.filter_by(id=userId).first()
        if not user:
            return jsonify({
                'status': 'error',
                'message': 'User not found'
            }), 404

        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)

        if page < 1:
            page = 1
        if per_page < 1 or per_page > 100:
            per_page = 10

        tickets = UserTicket.query.filter_by(assigned_to_empId=user.empId).order_by(UserTicket.date.desc()).all()

        total_tickets = len(tickets)
        total_pages = math.ceil(total_tickets / per_page) if total_tickets > 0 else 1

        start = (page - 1) * per_page
        end = start + per_page
        paginated = tickets[start:end]

        ticket_list = []
        for ticket in paginated:
            logs = [{
                'assigned_by': log.assigned_by_empId,
                'assigned_to': log.assigned_to_empId,
                'assigned_at': log.assigned_at.isoformat() if log.assigned_at else None
            } for log in ticket.assignment_logs]

            ticket_list.append({
                'ticket_id': ticket.id,
                'topic': ticket.topic,
                'problem': ticket.problem,
                'priority': ticket.priority,
                'department': ticket.department,
                'document': ticket.document,
                'status': ticket.status,
                'assigned_to_empId': ticket.assigned_to_empId,
                'created_by': ticket.userName,
                'date': ticket.date.isoformat() if ticket.date else None,
                'logs': logs
            })

        return jsonify({
            'status': 'success',
            'assigned_to': user.empId,
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
            'tickets': ticket_list
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({
            'status': 'error',
            'message': 'Internal Server Error',
            'error': str(e)
        }), 500



# ====================================
#     USER LEAVE CONTROL SECTION  - can control all leaves request and can also view and edit       
# ====================================


@superAdminBP.route('/userleave', methods=['GET'])
def user_leaves():
    try:
        superadmin, err, status = get_authorized_superadmin()
        if err:
            return err, status
        

        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        status_filter = request.args.get('status', '').strip().lower()
        department_filter = request.args.get('department', '').strip().lower()

        if page < 1:
            page = 1
        if per_page < 1 or per_page > 100:
            per_page = 10

        panel_users = superadmin.superadminPanel.allUsers

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
                if status_filter and leave.status and leave.status.lower() != status_filter:
                    continue
                if department_filter and user.department and user.department.lower() != department_filter:
                    continue

                all_leaves.append({
                    "userId": user.id,
                    "userName": user.userName,
                    "department" : user.department,
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

        all_leaves.sort(key=lambda x: x["appliedOnRaw"] or datetime.min, reverse=True)

        total_leaves = len(all_leaves)
        total_pages = math.ceil(total_leaves / per_page)
        start_index = (page - 1) * per_page
        end_index = start_index + per_page
        paginated_leaves = all_leaves[start_index:end_index]

        for leave in paginated_leaves:
            leave["appliedOn"] = leave["appliedOnRaw"].strftime('%Y-%m-%d') if leave["appliedOnRaw"] else None
            del leave["appliedOnRaw"]

        return jsonify({
            "status": "success",
            "message": "Leaves fetched successfully",
            "pagination": {
                "per_page": per_page,
                "total_leaves": total_leaves,
                "total_pages": total_pages,
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
        superadmin, err, status = get_authorized_superadmin()
        if err:
            return err, status

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

        socketio.emit(
            'leave_changes',
            {
                "title": "Leave Status Updated",
                "message": f"Your leave request from {leave.leavefrom} to {leave.leaveto} has been {leave.status}.",
                "status": leave.status,
                "leaveId": leave.id,
                "empId": leave.empId
            },
            room = leave.empId
        )
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
#         ADMIN LEAVE SECTION  - Admins all leaves policy      
# ====================================


@superAdminBP.route('/adminleave', methods=['POST'])
def addLeave():
    data = request.form

    if not data:
        return jsonify({"status": "error", "message": "No data provided"}), 400

    required_fields = ['leaveName', 'leaveType', 'calculationType', 'probation', 'day_type', 'carryforward', 'encashment', 'lapse_policy','max_leave_once', 'max_leave_year', 'monthly_leave_limit']

    if not all(field in data for field in required_fields):
        return jsonify({"status": "error", "message": "Please enter all required fields"}), 400

    try:
        superadmin, err, status = get_authorized_superadmin()
        if err:
            return err, status

        superadminpanelID = superadmin.superadminPanel.id
        checkleave = superadmin.superadminPanel.adminLeave

        if checkleave:
            return jsonify({"status": "error", "message": "Leave already exists. Please delete or update it."}), 409

        def str_to_bool(val):
            return str(val).lower() in ['true', '1', 'yes']

        newLeave = AdminLeave(
            superadminPanel=superadminpanelID,
            leaveName=data['leaveName'],
            leaveType=data['leaveType'],
            calculationType=data['calculationType'],
            probation=str_to_bool(data.get('probation')),
            day_type=data['day_type'],
            carryforward=str_to_bool(data.get('carryforward')),
            encashment=str_to_bool(data.get('encashment')),
            lapse_policy=str_to_bool(data.get('lapse_policy')),
            max_leave_once=int(data['max_leave_once']),
            max_leave_year=int(data['max_leave_year']),
            monthly_leave_limit=int(data['monthly_leave_limit']),
        )

        db.session.add(newLeave)
        db.session.commit()

        return jsonify({"status": "success", "message": "Leave created successfully"}), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({
            "status": "error",
            "message": "Internal Server Error",
            "error": str(e)
        }), 500


@superAdminBP.route('/adminleave/<int:id>', methods=['PUT'])
def editleave(id):
    print('Edit request hit')
    data = request.form

    if not data:
        return jsonify({"status": "error", "message": "No data provided"}), 400

    try:
        superadmin, err, status = get_authorized_superadmin()
        if err:
            return err, status

        panel_id = superadmin.superadminPanel.id

        leave = AdminLeave.query.filter_by(id=id, superadminPanel=panel_id).first()
        if not leave:
            return jsonify({"status": "error", "message": "Leave not found"}), 404

        def str_to_bool(val):
            return str(val).lower() in ['true', '1', 'yes']

        # leave.leaveStatus = data.get('leaveStatus', leave.leaveStatus)
        leave.leaveType = data.get('leaveType', leave.leaveType)
        leave.calculationType = data.get('calculationType', leave.calculationType)
        leave.probation = str_to_bool(data.get('probation', leave.probation))
        leave.day_type = data.get('day_type', leave.day_type)
        leave.carryforward = str_to_bool(data.get('carryforward', leave.carryforward))
        leave.encashment = str_to_bool(data.get('encashment', leave.encashment))

        db.session.commit()

        return jsonify({"status": "success", "message": "Leave updated successfully"}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({
            "status": "error",
            "message": "Internal Server Error",
            "error": str(e)
        }), 500


@superAdminBP.route('/adminleave', methods=['GET'])
def get_leaveDetails():
    try:
        superadmin, err, status = get_authorized_superadmin()
        if err:
            return err, status

        panel = superadmin.superadminPanel

        leavedetails = panel.adminLeave
        if not leavedetails:
            return jsonify({"status": "error", "message": "No leave details found"}), 200
        
        leavelist=[]
        for leave in leavedetails:
                leavelist.append({
                    "id": leave.id,
                    "leaveType": leave.leaveType,
                    "leaveName": leave.leaveName,
                    "calculationType": leave.calculationType,
                    "probation": leave.probation,
                    "day_type": leave.day_type,
                    "carryforward": leave.carryforward,
                    "encashment": leave.encashment,
                    "max_leave_once" : leave.max_leave_once,
                    "max_leave_year" : leave.max_leave_year,
                })

        return jsonify({
            "status": "success",
            "message": "Fetched leave details successfully",
            "data": leavelist
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({
            "status": "error",
            "message": "Internal server error",
            "error": str(e)
        }), 500


@superAdminBP.route('/adminleave/<int:id>', methods=['DELETE'])
def delete_leave(id):
    try:
        superadmin, err, status = get_authorized_superadmin()
        if err:
            return err, status

        panel_id = superadmin.superadminPanel.id

        leave = AdminLeave.query.filter_by(id=id, superadminPanel=panel_id).first()
        if not leave:
            return jsonify({"status": "error", "message": "Leave not found"}), 404

        db.session.delete(leave)
        db.session.commit()

        return jsonify({"status": "success", "message": "Leave deleted successfully"}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({
            "status": "error",
            "message": "Internal server error",
            "error": str(e)
        }), 500



# ====================================
#         DOCUMENT SECTION      - admin all documents 
# ====================================


@superAdminBP.route('/documents', methods=['POST'])
def documents():
    title = request.form.get('title', '')
    files = request.files.get('document')
    try:
        superadmin, err, status = get_authorized_superadmin()
        if err:
            return err, status
        
        superpanelD = superadmin.superadminPanel.id

        result = cloudinary.uploader.upload(files)
        doc_url = result.get("secure_url")

        adminDocs = AdminDoc(
            superadminPanel= superpanelD,
            document = doc_url,
            title = title
        )

        db.session.add(adminDocs)
        db.session.commit()

        return jsonify({"status" : "success", "message" : "Uploaded successfully", "document" : {"doc_url" : doc_url, "title" : title}}),201

    except Exception as e:
        return jsonify({"status" : "error", "message" : "Internal Server Error", "error" : str(e)}), 500


@superAdminBP.route('/documents/<int:id>', methods=['PUT'])
def edit_document(id):
    try:
        superadmin, err, status = get_authorized_superadmin()
        if err:
            return err, status

        adminDocs = AdminDoc.query.filter_by(id=id).first()
        if not adminDocs:
            return jsonify({"status": "error", "message": "No Admin documents found with these details"}), 409

        title = request.form.get('title')
        document = request.files.get('documents')

        if title:
            adminDocs.title = title

        if document:
            result = cloudinary.uploader.upload(document)
            doc_url = result.get('secure_url')
            adminDocs.document = doc_url

        db.session.commit()

        return jsonify({"status": "success", "message": "Updated Successfully"}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": "Internal Server Error", "error": str(e)}), 500


@superAdminBP.route('/documents', methods=['GET'])
def document_details():
    try:
        superadmin, err, status = get_authorized_superadmin()
        if err:
            return err, status

        admindocs = superadmin.superadminPanel.id

        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 10))

        pagination = AdminDoc.query.filter_by(superadminPanel=admindocs).paginate(page=page, per_page=limit, error_out=False)

        documentList = [
            {
                "id" : doc.id,
                "documents": doc.document,
                "title": doc.title
            }
            for doc in pagination.items
        ]

        return jsonify({
            "status": "success",
            "message": "Fetched successfully",
            "documents": documentList,
            "total": pagination.total,
            "page": pagination.page,
            "limit": pagination.per_page,
            "pages": pagination.pages
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": "Internal Server Error", "error": str(e)}), 500


@superAdminBP.route('/documents/<int:id>', methods=['DELETE'])
def delete_details(id):
    try:
        superadmin, err, status = get_authorized_superadmin()
        if err:
            return err, status
        
        adminDocs = AdminDoc.query.filter_by(id=id).first()
        if not adminDocs:
            return jsonify({"status": "error", "message": "No Docs found"}), 400
        
        db.session.delete(adminDocs)
        db.session.commit()

        return jsonify({
            "status": "success",
            "message": "Deleted successfully",
        }), 200
    
    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": "Internal Server Error", "error": str(e)}), 500



# ====================================
#            ANNOUNCE SECTION       - admin all announcements can also see who likes, polls and comments  
# ====================================


@superAdminBP.route('/announcement', methods=['POST'])
def create_announcement():
    try:
        superadmin, err, status = get_authorized_superadmin()
        if err:
            return err, status

        title = request.form.get('title')
        content = request.form.get('content')
        scheduled_time = request.form.get('scheduled_time')
        poll_question = request.form.get('poll_question')

        poll_options_raw = request.form.get('poll_options')
        if poll_options_raw:
            try:
                import json
                poll_options = json.loads(poll_options_raw)
                if not isinstance(poll_options, list):
                    raise ValueError
            except Exception:
                return jsonify({
                    "status": "error",
                    "message": "Invalid poll_options format. Must be a JSON array like [\"A\", \"B\"]"
                }), 400
        else:
            poll_options = []

        if not title:
            return jsonify({"status": "error", "message": "Title is required"}), 400

        publish_now = True
        parsed_schedule = None
        if scheduled_time:
            try:
                fixed_time = scheduled_time.replace("+05+30", "+05:30")
                parsed_schedule = parser.isoparse(fixed_time)
                publish_now = False
            except (ValueError, TypeError):
                return jsonify({
                    "status": "error",
                    "message": "Invalid scheduled_time format (use ISO 8601 like 2025-06-18T15:25:00+05:30)"
                }), 400

        uploaded_images = []
        if 'images' in request.files:
            images = request.files.getlist('images')
            for image in images:
                if image:
                    upload_result = cloudinary.uploader.upload(image)
                    uploaded_images.append(upload_result['secure_url'])

        video_url = None
        if 'video' in request.files:
            video_file = request.files['video']
            if video_file:
                video_upload = cloudinary.uploader.upload(
                    video_file,
                    resource_type='video'
                )
                video_url = video_upload['secure_url']

        poll_option_1 = poll_options[0] if len(poll_options) > 0 else None
        poll_option_2 = poll_options[1] if len(poll_options) > 1 else None
        poll_option_3 = poll_options[2] if len(poll_options) > 2 else None
        poll_option_4 = poll_options[3] if len(poll_options) > 3 else None

        announcement = Announcement(
            title=title,
            content=content,
            scheduled_time=parsed_schedule,
            is_published=publish_now,
            created_at=datetime.utcnow(),
            adminPanelId=superadmin.superadminPanel.id,
            poll_question=poll_question,
            poll_option_1=poll_option_1,
            poll_option_2=poll_option_2,
            poll_option_3=poll_option_3,
            poll_option_4=poll_option_4,
            images=uploaded_images,
            video=video_url
        )

        db.session.add(announcement)
        db.session.commit()

        socketio.emit(
            'notification',
            {
                'title': 'New Announcement 📣',
                'message': 'A new announcement has been published by your admin.',
            },
            room=f"panel_{superadmin.superadminPanel.id}"
        )

        return jsonify({"status": "success", "message": "Announcement created successfully"}), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({
            "status": "error",
            "message": "Server error",
            "error": str(e)
        }), 500


@superAdminBP.route('/announcement/<int:id>', methods=['DELETE'])
def delete_announcement(id):
    try:
        superadmin, err, status = get_authorized_superadmin()
        if err:
            return err, status

        announcement = Announcement.query.get(id)
        if not announcement:
            return jsonify({
                "status": "error",
                "message": f"Announcement with ID {id} not found."
            }), 404

        db.session.delete(announcement)
        db.session.commit()

        return jsonify({
            "status": "success",
            "message": f"Announcement with ID {id} has been deleted."
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({
            "status": "error",
            "message": "Server error",
            "error": str(e)
        }), 500


@superAdminBP.route('/announcement', methods=['GET'])
def get_announcement():
    try:
        superadmin, err, status = get_authorized_superadmin(
            required_section="announcement",
            required_permissions="view"
        )
        if err:
            return err, status

        userID = g.user.get('userID') if g.user else None
        if not userID:
            return jsonify({"status": "error", "message": "No user token found"}), 401

        allAnnouncement = superadmin.superadminPanel.adminAnnouncement

        filtered_announcements = sorted(
            [ann for ann in allAnnouncement if ann.is_published and (not ann.scheduled_time or ann.scheduled_time <= datetime.utcnow())],
            key=lambda x: x.created_at,
            reverse=True
        )

        result = []
        for ann in filtered_announcements:
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
                    ]
                } if ann.poll_question else None
            })

        return jsonify({
            "status": "success",
            "message": "Fetched published announcements",
            "data": result
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({
            "status": "error",
            "message": "Internal Server Error",
            "error": str(e)
        }), 500



# ====================================
#         BONUS SECTION              - admin bonus section where admin can create his own bonus policies  
# ====================================

@superAdminBP.route('/bonus', methods=['POST'])
def add_bonus():
    data = request.get_json()
    if not data:
        return jsonify({
            "status": "error",
            "message": "No data provided"
        }), 400

    required_fields = ['bonus_name', 'bonus_method', 'amount']
    if not all(field in data for field in required_fields):
        return jsonify({
            'status': "error",
            "message": "All required fields (bonus_name, bonus_method, amount) must be provided"
        }), 400

    try:
        superadmin, err, status = get_authorized_superadmin()
        if err:
            return err, status

        if superadmin.superadminPanel.adminBonusPolicy:
            return jsonify({
                "status": "error",
                "message": "Policy already exists. Update or delete it."
            }), 400

        superpanelid = superadmin.superadminPanel.id

        bonus_policy = BonusPolicy(
            superPanelID=superpanelid,
            bonus_name=data['bonus_name'],
            bonus_method=data['bonus_method'],
            amount=int(data['amount']),
            employeement_type=data.get('employeement_type') or None,
            department_type=data.get('department_type') or None
        )

        db.session.add(bonus_policy)
        db.session.commit()

        return jsonify({
            "status": "success",
            "message": "Bonus policy added successfully"
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({
            "status": "error",
            "message": "Internal Server Error",
            "error": str(e)
        }), 500


@superAdminBP.route('/bonus', methods=['GET'])
def get_bonus():
    try:
        superadmin, err, status = get_authorized_superadmin()
        if err:
            return err, status

        active_panel = superadmin.superadminPanel

        if not active_panel.adminBonusPolicy:
            return jsonify({
                "status": "error",
                "message": "No bonus policies found"
            }), 200

        bonusList = []
        for bonuss in active_panel.adminBonusPolicy:
            bonusList.append({
                "id": bonuss.id,
                "name": bonuss.bonus_name,
                "method": bonuss.bonus_method,
                "amount": bonuss.amount,
                "applyOn": bonuss.apply,
                "department_type": bonuss.department_type,
                "employeement_type": bonuss.employeement_type,
            })

        return jsonify({
            "status": "success",
            "data": bonusList,
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

    allowed_fields = ['bonus_name', 'apply',"bonus_method", 'amount', 'employeement_type', 'department_type']
    if not any(field in data for field in allowed_fields):
        return jsonify({
            "status": "error",
            "message": "At least one field must be provided to update"
        }), 400

    try:
        superadmin, err, status = get_authorized_superadmin()
        if err:
            return err, status

        superpanelid = superadmin.superadminPanel.id

        bonuspolicy = BonusPolicy.query.filter_by(id=id, superPanelID=superpanelid).first()
        if not bonuspolicy:
            return jsonify({
                "status": "error",
                "message": "No bonus policy found"
            }), 404

        if 'bonus_name' in data:
            bonuspolicy.bonus_name = data['bonus_name']
        if 'apply' in data:
            bonuspolicy.apply = data['apply']
        if 'bonus_methods' in data:
            bonuspolicy.bonus_method = data['bonus_method']
        if 'amount' in data:
            bonuspolicy.amount = int(data['amount'])
        if 'employeement_type' in data:
            bonuspolicy.employeement_type = data['employeement_type']
        if 'department_type' in data:
            bonuspolicy.department_type = data['department_type']

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
        superadmin, err, status = get_authorized_superadmin()
        if err:
            return err, status

        superpanelid = superadmin.superadminPanel.id

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
#      SHIFT AND TIME SECTION          -  admin shift and time management section where admin can manage time   
# ====================================

@superAdminBP.route('/shift_time', methods=['POST'])
def addshift():
    try:
        superadmin, err, status = get_authorized_superadmin()
        if err:
            return err, status

        data = request.get_json()
        required_fields = [
            'shiftName', 'shiftType', 'shiftStatus', 'shiftStart', 'shiftEnd',
            'GraceTime', 'MaxEarly', 'MaxLateEntry', 'HalfDayThreshhold',
            'OverTimeCountAfter'
        ]

        if not data or not all(field in data for field in required_fields):
            return jsonify({
                "status": "error",
                "message": f"Missing fields. Required: {required_fields}"
            }), 400

        shift_type = data['shiftType']
        shift_status = bool(data['shiftStatus'])
        working_days = data.get('workingDays')
        saturday_condition = data.get('saturdayCondition')

        if shift_status:
            existing_active_shift = ShiftTimeManagement.query.filter_by(
                shiftType=shift_type,
                shiftStatus=True,
                superpanel=superadmin.superadminPanel.id
            ).first()

            if existing_active_shift:
                return jsonify({
                    "status": "error",
                    "message": f"An active shift with type '{shift_type}' already exists."
                }), 409

        time_format = '%Y-%m-%d %I:%M:%S %p'  # 12-hour with AM/PM

        shift = ShiftTimeManagement(
            shiftName=data['shiftName'],
            shiftType=shift_type,
            shiftStatus=shift_status,
            shiftStart=datetime.strptime(data['shiftStart'], time_format),
            shiftEnd=datetime.strptime(data['shiftEnd'], time_format),
            GraceTime=datetime.strptime(data['GraceTime'], time_format),
            MaxEarly=datetime.strptime(data['MaxEarly'], time_format),
            MaxLateEntry=datetime.strptime(data['MaxLateEntry'], time_format),
            HalfDayThreshhold=datetime.strptime(data['HalfDayThreshhold'], time_format),
            OverTimeCountAfter=datetime.strptime(data['OverTimeCountAfter'], time_format),
            Biometric=data.get('Biometric', False),
            RemoteCheckIn=data.get('RemoteCheckIn', False),
            ShiftSwap=data.get('ShiftSwap', False),
            workingDays=working_days if isinstance(working_days, list) else None,
            saturdayCondition=saturday_condition,
            superpanel=superadmin.superadminPanel.id
        )

        db.session.add(shift)
        db.session.commit()

        return jsonify({
            "status": "success",
            "message": "Shift added successfully",
            "shift_id": shift.id
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({
            "status": "error",
            "message": "Internal Server Error",
            "error": str(e)
        }), 500


@superAdminBP.route('/shift_time', methods=['GET'])
def get_shift_policy():
    try:
        superadmin, err, status = get_authorized_superadmin()
        if err:
            return err, status

        shiftpolicy = superadmin.superadminPanel.adminTimePolicy
        if not shiftpolicy or len(shiftpolicy) == 0:
            return jsonify({
                "status": "error",
                "message": "No shift policies found",
            }), 200

        shiftlist = []
        for shift in shiftpolicy:
            shiftlist.append({
                "id": shift.id,
                "shiftName": shift.shiftName,
                "shiftType": shift.shiftType,
                "shiftStatus": shift.shiftStatus,
                "shiftStart": shift.shiftStart.strftime('%Y-%m-%d %I:%M:%S %p') if shift.shiftStart else None,
                "shiftEnd": shift.shiftEnd.strftime('%Y-%m-%d %I:%M:%S %p') if shift.shiftEnd else None,
                "GraceTime": shift.GraceTime.strftime('%Y-%m-%d %I:%M:%S %p') if shift.GraceTime else None,
                "MaxEarly": shift.MaxEarly.strftime('%Y-%m-%d %I:%M:%S %p') if shift.MaxEarly else None,
                "MaxLateEntry": shift.MaxLateEntry.strftime('%Y-%m-%d %I:%M:%S %p') if shift.MaxLateEntry else None,
                "HalfDayThreshhold": shift.HalfDayThreshhold.strftime('%Y-%m-%d %I:%M:%S %p') if shift.HalfDayThreshhold else None,
                "OverTimeCountAfter": shift.OverTimeCountAfter.strftime('%Y-%m-%d %I:%M:%S %p') if shift.OverTimeCountAfter else None,
                "Biometric": shift.Biometric,
                "RemoteCheckIn": shift.RemoteCheckIn,
                "ShiftSwap": shift.ShiftSwap,
                "workingDays": shift.workingDays if shift.workingDays else [],
                "saturdayCondition": shift.saturdayCondition
            })

        return jsonify({
            "status": "success",
            "message": "Shifts fetched successfully",
            "data": shiftlist
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({
            "status": "error",
            "message": "Internal Server Error",
            "error": str(e)
        }), 500


@superAdminBP.route('/shift_time/<int:shift_id>', methods=['DELETE'])
def delete_shift_policy(shift_id):
    try:
        superadmin, err, status = get_authorized_superadmin()
        if err:
            return err, status

        shift = ShiftTimeManagement.query.filter_by(id=shift_id, superpanel=superadmin.superadminPanel.id).first()
        if not shift:
            return jsonify({
                "status": "error",
                "message": "Shift not found or unauthorized"
            }), 404

        db.session.delete(shift)
        db.session.commit()

        return jsonify({
            "status": "success",
            "message": "Shift policy deleted successfully"
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({
            "status": "error",
            "message": "Internal Server Error",
            "error": str(e)
        }), 500


@superAdminBP.route('/shift_time/<int:shift_id>', methods=['PUT'])
def edit_shift_policy(shift_id):
    try:
        superadmin, err, status = get_authorized_superadmin()
        if err:
            return err, status

        data = request.get_json()
        if not data:
            return jsonify({
                "status": "error",
                "message": "No data provided"
            }), 400

        shift = ShiftTimeManagement.query.filter_by(
            id=shift_id,
            superpanel=superadmin.superadminPanel.id
        ).first()

        if not shift:
            return jsonify({
                "status": "error",
                "message": "Shift policy not found or unauthorized"
            }), 404

        updatable_fields = [
            'shiftName', 'shiftType', 'shiftStatus', 'shiftStart', 'shiftEnd',
            'GraceTime', 'MaxEarly', 'MaxLateEntry', 'HalfDayThreshhold',
            'OverTimeCountAfter', 'Biometric', 'RemoteCheckIn', 'ShiftSwap',
            'workingDays', 'saturdayCondition'
        ]

        time_format = '%Y-%m-%d %I:%M:%S %p'

        for field in updatable_fields:
            if field in data:
                value = data[field]

                if field in [
                    'shiftStart', 'shiftEnd', 'GraceTime', 'MaxEarly',
                    'MaxLateEntry', 'HalfDayThreshhold', 'OverTimeCountAfter'
                ]:
                    try:
                        value = datetime.strptime(value, time_format)
                    except Exception:
                        return jsonify({
                            "status": "error",
                            "message": f"Invalid datetime format for {field}, expected format: {time_format}"
                        }), 400

                if field == 'workingDays':
                    if not isinstance(value, list):
                        return jsonify({
                            "status": "error",
                            "message": "workingDays must be a list of weekdays"
                        }), 400

                if field == 'saturdayCondition':
                    allowed_conditions = ['every', 'alternate', 'first_last', 'none']
                    if value.lower() not in allowed_conditions:
                        return jsonify({
                            "status": "error",
                            "message": f"saturdayCondition must be one of {allowed_conditions}"
                        }), 400

                setattr(shift, field, value)

        db.session.commit()

        return jsonify({
            "status": "success",
            "message": "Shift policy updated successfully"
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({
            "status": "error",
            "message": "Internal Server Error",
            "error": str(e)
        }), 500




# ====================================
#      REMOTE WORK SECTION         - admin can also set remote work polciy
# ====================================


@superAdminBP.route('/remotework', methods=['POST'])
def add_remoteWork():
    try:
        superadmin, err, status = get_authorized_superadmin()
        if err:
            return err, status

        existing_policy = RemotePolicy.query.filter_by(superPanel=superadmin.superadminPanel.id).first()
        if existing_policy:
            return jsonify({
                "status": "error",
                "message": "Remote work policy already exists for this superadmin."
            }), 400

        # Get data from request
        data = request.get_json()
        required_fields = ['remoteName', 'max_remote_day', 'allowed_department']

        if not data or not all(field in data for field in required_fields):
            return jsonify({
                "status": "error",
                "message": f"Missing required fields: {', '.join(required_fields)}"
            }), 400

        # Create new RemotePolicy instance
        new_policy = RemotePolicy(
            remoteName=data.get('remoteName'),
            remoteStatus=data.get('remoteStatus', False),
            max_remote_day=data.get('max_remote_day'),
            approval=data.get('approval', False),
            allowed_department=data.get('allowed_department'),
            equipment_provided=data.get('equipment_provided', False),
            superPanel=superadmin.superadminPanel.id
        )

        db.session.add(new_policy)
        db.session.commit()

        return jsonify({
            "status": "success",
            "message": "Remote work policy created successfully."
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({
            "status": "error",
            "message": "Internal Server Error",
            "error": str(e)
        }), 500


@superAdminBP.route('/remotework', methods=['GET'])
def get_remote_work():
    try:
        superadmin, err, status = get_authorized_superadmin()
        if err:
            return err, status

        policy = RemotePolicy.query.filter_by(superPanel=superadmin.superadminPanel.id).first()
        if not policy:
            return jsonify({"status": "error", "message": "Remote policy not found"}), 404

        return jsonify({
            "status": "success",
            "data": {
                "id": policy.id,
                "remoteName": policy.remoteName,
                "remoteStatus": policy.remoteStatus,
                "max_remote_day": policy.max_remote_day,
                "approval": policy.approval,
                "allowed_department": policy.allowed_department,
                "equipment_provided": policy.equipment_provided,
                "superPanel": policy.superPanel
            }
        }), 200

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@superAdminBP.route('/remotework/<int:id>', methods=['PUT'])
def update_remote_work(id):
    try:
        data = request.get_json()
        superadmin, err, status = get_authorized_superadmin()
        if err:
            return err, status

        policy = RemotePolicy.query.filter_by(id=id, superPanel=superadmin.superadminPanel.id).first()
        if not policy:
            return jsonify({"status": "error", "message": "Policy not found"}), 404

        updatable_fields = ['remoteName', 'remoteStatus', 'max_remote_day', 'approval', 'allowed_department', 'equipment_provided']
        for field in updatable_fields:
            if field in data:
                setattr(policy, field, data[field])

        db.session.commit()

        return jsonify({"status": "success", "message": "Remote policy updated"}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500


@superAdminBP.route('/remotework/<int:id>', methods=['DELETE'])
def delete_remote_work(id):
    try:
        superadmin, err, status = get_authorized_superadmin()
        if err:
            return err, status

        policy = RemotePolicy.query.filter_by(id=id, superPanel=superadmin.superadminPanel.id).first()
        if not policy:
            return jsonify({"status": "error", "message": "Policy not found"}), 404

        db.session.delete(policy)
        db.session.commit()

        return jsonify({"status": "success", "message": "Remote policy deleted"}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500




# ====================================
#      PAYROLL SECTION         -  admin payroll policies
# ====================================


@superAdminBP.route('/payroll', methods=['POST'])
def add_payroll():
    try:
        userID = g.user.get('userID') if g.user else None
        if not userID:
            return jsonify({
                "status": "error",
                "message": "No user ID or auth token"
            }), 404

        # Check if user is SuperAdmin or HR under a SuperAdmin
        superadmin = SuperAdmin.query.filter_by(id=userID).first()
        if not superadmin:
            user = User.query.filter_by(id=userID).first()
            if not user or user.userRole.lower() != 'hr':
                return jsonify({
                    "status": "error",
                    "message": "Unauthorized"
                }), 409
            superadmin = SuperAdmin.query.filter_by(superId=user.superadminId).first()
            if not superadmin:
                return jsonify({
                    "status": "error",
                    "message": "No superadmin found"
                }), 404

        data = request.get_json()
        if not data:
            return jsonify({
                "status": "error",
                "message": "No data provided"
            }), 400

        required_fields = [
            'calculation_method', 'overtimePolicy', 'perhour',
            'pfDeduction', 'salaryHoldCondition', 'disbursement',
            'employeementType', 'departmentType'
        ]
        if not all(field in data for field in required_fields):
            return jsonify({
                "status": "error",
                "message": "Missing required fields"
            }), 400

        try:
            disbursement = datetime.fromisoformat(data['disbursement'])
        except ValueError:
            return jsonify({
                "status": "error",
                "message": "Invalid disbursement datetime format. Use ISO 8601."
            }), 400

        policy = PayrollPolicy(
            policyname = data['policyname'],
            calculation_method=data['calculation_method'],
            overtimePolicy=data['overtimePolicy'],
            perhour=data['perhour'],
            pfDeduction=data['pfDeduction'],
            salaryHoldCondition=data['salaryHoldCondition'],  # should be a list/array
            disbursement=disbursement,
            employeementType=data['employeementType'],
            departmentType=data['departmentType'],
            superpanel=superadmin.id
        )

        db.session.add(policy)
        db.session.commit()

        return jsonify({
            "status": "success",
            "message": "Payroll policy added successfully"
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({
            "status": "error",
            "message": "Internal Server Error",
            "error": str(e)
        }), 500
    

@superAdminBP.route('/payroll', methods=['GET'])
def get_payrolls():
    try:
        superadmin, err, status = get_authorized_superadmin()
        if err:
            return err, status

        payrolls = PayrollPolicy.query.filter_by(superpanel=superadmin.superadminPanel.id).all()
        results = [{
            "id": p.id,
            "calculation_method": p.calculation_method,
            "overtimePolicy": p.overtimePolicy,
            "perhour": p.perhour,
            "pfDeduction": p.pfDeduction,
            "salaryHoldCondition": p.salaryHoldCondition,
            "disbursement": p.disbursement.isoformat() if p.disbursement else None,
            "employeementType": p.employeementType,
            "departmentType": p.departmentType,
            "policyname": p.policyname,
        } for p in payrolls]

        return jsonify({"status": "success", "data": results}), 200

    except Exception as e:
        return jsonify({"status": "error", "message": "Server error", "error": str(e)}), 500


@superAdminBP.route('/payroll/<int:id>', methods=['PUT'])
def update_payroll(id):
    try:
        superadmin, err, status = get_authorized_superadmin()
        if err:
            return err, status

        policy = PayrollPolicy.query.filter_by(id=id, superpanel=superadmin.superadminPanel.id).first()
        if not policy:
            return jsonify({"status": "error", "message": "Payroll policy not found"}), 404

        data = request.get_json()
        if not data:
            return jsonify({"status": "error", "message": "No data provided"}), 400

        # Update fields if present
        for field in [
            'calculation_method', 'overtimePolicy', 'perhour', 'pfDeduction',
            'salaryHoldCondition', 'employeementType', 'departmentType', 'policyname'
        ]:
            if field in data:
                setattr(policy, field, data[field])

        if 'disbursement' in data:
            try:
                policy.disbursement = datetime.fromisoformat(data['disbursement'])
            except ValueError:
                return jsonify({"status": "error", "message": "Invalid disbursement format"}), 400

        db.session.commit()
        return jsonify({"status": "success", "message": "Payroll policy updated"}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": "Server error", "error": str(e)}), 500


@superAdminBP.route('/payroll/<int:id>', methods=['DELETE'])
def delete_payroll(id):
    try:
        superadmin, err, status = get_authorized_superadmin()
        if err:
            return err, status

        policy = PayrollPolicy.query.filter_by(id=id, superpanel=superadmin.superadminPanel.id).first()
        if not policy:
            return jsonify({"status": "error", "message": "Payroll policy not found"}), 404

        db.session.delete(policy)
        db.session.commit()
        return jsonify({"status": "success", "message": "Payroll policy deleted"}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": "Server error", "error": str(e)}), 500




# ====================================
#          NOTICE SECTION         - admin can create notice 
# ====================================


@superAdminBP.route('/notice', methods=['POST'])
def add_notice():
    try:
        superadmin, err, status = get_authorized_superadmin()
        if err:
            return err, status

        data = request.get_json()
        if not data or not data.get('notice'):
            return jsonify({"status": "error", "message": "Notice content is required"}), 400

        new_notice = Notice(
            id=int(datetime.utcnow().timestamp()),
            superpanel=superadmin.superadminPanel.id,
            notice=data['notice']
        )

        db.session.add(new_notice)
        db.session.commit()

        socketio.emit(
            'notification',
            {
                'title': '📌 New Notice',
                'message': data['notice']
            },
            room=f"panel_{superadmin.superadminPanel.id}"
        )

        return jsonify({
            "status": "success",
            "message": "Notice added and notification sent successfully"
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({
            "status": "error",
            "message": "Internal Server Error",
            "error": str(e),
        }), 500


@superAdminBP.route('/notice', methods=['GET'])
def get_notices():
    try:
        superadmin, err, status = get_authorized_superadmin()
        if err:
            return err, status

        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 10))
        offset = (page - 1) * limit

        total_notices = Notice.query.filter_by(superpanel=superadmin.superadminPanel.id).count()
        notices = Notice.query.filter_by(superpanel=superadmin.superadminPanel.id)\
                              .order_by(Notice.createdAt.desc())\
                              .offset(offset).limit(limit).all()

        notice_list = [
            {
                "id": notice.id,
                "notice": notice.notice,
                "date": notice.createdAt,
            }
            for notice in notices
        ]

        return jsonify({
            "status": "success",
            "data": notice_list,
            "pagination": {
                "current_page": page,
                "limit": limit,
                "total_records": total_notices,
                "total_pages": (total_notices + limit - 1) // limit
            }
        }), 200

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": "Internal Server Error",
            "error": str(e),
        }), 500


@superAdminBP.route('/notice/<int:notice_id>', methods=['DELETE'])
def delete_notice(notice_id):
    try:
        superadmin, err, status = get_authorized_superadmin()
        if err:
            return err, status

        notice = Notice.query.filter_by(id=notice_id, superpanel=superadmin.superadminPanel.id).first()
        if not notice:
            return jsonify({"status": "error", "message": "Notice not found"}), 404

        db.session.delete(notice)
        db.session.commit()

        return jsonify({
            "status": "success",
            "message": "Notice deleted successfully"
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({
            "status": "error",
            "message": "Internal Server Error",
            "error": str(e),
        }), 500




# ====================================
#      EMPLOYEE DOC SECTION           - admin can view employee docs
# ====================================


@superAdminBP.route('/employee_document', methods=['GET'])
def get_employee_documents():
    try:
        superadmin, err, status = get_authorized_superadmin()
        if err:
            return err, status

        user_id = request.args.get('id', type=int)
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 10))
        search_query = request.args.get('search', '').lower()
        offset = (page - 1) * limit

        users = superadmin.superadminPanel.allUsers

        all_documents = []
        matched_user_found = False

        for user in users:
            if user_id:
                if user.id != user_id:
                    continue
                matched_user_found = True

            if search_query and search_query not in user.userName.lower():
                continue

            panel_data = user.panelData
            if not panel_data:
                continue

            documents = panel_data.UserDocuments
            for doc in documents:
                all_documents.append({
                    "user_id": user.id,
                    "user_name": user.userName,
                    "document_id": doc.id,
                    "document_name": doc.documents,
                    "document_url": doc.title,
                })

        # Handle case: user_id was given but not found
        if user_id and not matched_user_found:
            return jsonify({
                "status": "error",
                "message": f"No user found with id {user_id}"
            }), 404

        total_documents = len(all_documents)
        paginated_docs = all_documents[offset:offset + limit]

        return jsonify({
            "status": "success",
            "data": paginated_docs,
            "pagination": {
                "current_page": page,
                "limit": limit,
                "total_records": total_documents,
                "total_pages": (total_documents + limit - 1) // limit
            }
        }), 200

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": "Internal Server error",
            "error": str(e),
        }), 500




# ====================================
#      PROJECT MANAGEMENT SECTION           - admin can create projects 
# ====================================


@superAdminBP.route('/project', methods=['POST'])
def add_Project():
    try:
        userID = g.user.get('userID') if g.user else None
        if not userID:
            return None, jsonify({"status": "error", "message": "No auth token"}), 401

        superadmin = SuperAdmin.query.filter_by(id=userID).first()
        if not superadmin:
            user = User.query.filter_by(id=userID).first()
            if not user or user.userRole.lower() != 'teamlead':
                return None, jsonify({"status": "error", "message": "Unauthorized"}), 403
            
            superadmin = SuperAdmin.query.filter_by(superId=user.superadminId).first()
            if not superadmin:
                return None, jsonify({"status": "error", "message": "No superadmin found"}), 404

        title = request.form.get('title')
        description = request.form.get('description')
        lastDate = request.form.get('lastDate')
        status = request.form.get('status')
        links = request.form.getlist('links') or []
        files = request.form.getlist('files') or []
        emp_ids = request.form.getlist('empIDs')

        if not title or not lastDate:
            return jsonify({
                "status": "error",
                "message": "Title and Last Date are required."
            }), 400

        try:
            lastDate_dt = datetime.fromisoformat(lastDate)
        except ValueError:
            return jsonify({
                "status": "error",
                "message": "Invalid date format for 'lastDate'. Use YYYY-MM-DD or ISO."
            }), 400

        new_task = TaskManagement(
            superpanelId=superadmin.superadminPanel.id,
            title=title,
            description=description,
            lastDate=lastDate_dt,
            status=status,
            links=links,
            files=files
        )
        db.session.add(new_task)
        db.session.flush()

        assigned_users = []

        for emp_id in emp_ids:
            user = User.query.filter_by(empId=emp_id).first()
            if not user:
                continue
            if user and user.panelData:
                user_panel = user.panelData
                task_user = TaskUser(
                    taskPanelId=new_task.id,
                    userPanelId=user_panel.id,
                    user_emp_id=user.empId,
                    user_userName=getattr(user, 'userName', 'Unknown'),
                    image=getattr(user, 'profileImage', '')
                )
                db.session.add(task_user)

                socketio.emit(
                    'notification',
                    {
                        'title': '📌 New Project Assigned',
                        'message': f'You have been assigned to project: {title}',
                        'taskId': new_task.id,
                        'type': 'task'
                    },
                    room=emp_id
                )

                assigned_users.append({
                    "emp_id": user.empId,
                    "userName": user.userName,
                    "profileImage": user.profileImage
                })

        db.session.commit()

        return jsonify({
            "status": "success",
            "message": "Project and task assignments added successfully",
            "taskId": new_task.id,
            "assigned_to": assigned_users
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({
            "status": "error",
            "message": "Internal Server Error",
            "error": str(e)
        }), 500


@superAdminBP.route('/project', methods=['GET'])
def get_all_projects():
    try:
        superadmin, err, status = get_authorized_superadmin()
        if err:
            return err, status

        tasks = TaskManagement.query.filter_by(
            superpanelId=superadmin.superadminPanel.id
        ).order_by(TaskManagement.assignedAt.desc()).all()

        task_list = []
        for task in tasks:
            assigned_users = []
            all_completed = True

            for user in task.users:
                assigned_users.append({
                    "userPanelId": user.userPanelId,
                    "empId": user.user_emp_id,
                    "userName": user.user_userName,
                    "image": user.image,
                    "isCompleted": user.is_completed
                })

                if not user.is_completed:
                    all_completed = False

            task_status = task.status

            comments = []
            for comment in task.comments:
                comments.append({
                    "id": comment.id,
                    "userId": comment.userId,
                    "username": comment.username,
                    "comment": comment.comments,
                    "timestamp": comment.timestamp.isoformat() if hasattr(comment, "timestamp") and comment.timestamp else None
                })

            task_list.append({
                "id": task.id,
                "title": task.title,
                "description": task.description,
                "assignedAt": task.assignedAt.isoformat() if task.assignedAt else None,
                "lastDate": task.lastDate.isoformat() if task.lastDate else None,
                "links": task.links,
                "files": task.files,
                "status": task_status,
                "comments": comments,
                "assignedUsers": assigned_users
            })

        return jsonify({
            "status": "success",
            "tasks": task_list
        }), 200

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": "Internal Server Error",
            "error": str(e)
        }), 500


@superAdminBP.route('/project/<int:task_id>', methods=['DELETE'])
def delete_project(task_id):
    try:
        superadmin, err, status = get_authorized_superadmin()
        if err:
            return err, status

        task = TaskManagement.query.filter_by(
            id=task_id,
            superpanelId=superadmin.superadminPanel.id
        ).first()

        if not task:
            return jsonify({
                "status": "error",
                "message": "Task not found or unauthorized"
            }), 404

        db.session.delete(task)
        db.session.commit()

        return jsonify({
            "status": "success",
            "message": "Project and all associated comments deleted successfully"
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({
            "status": "error",
            "message": "Internal Server Error",
            "error": str(e)
        }), 500


@superAdminBP.route('/project/<int:task_id>', methods=['PUT'])
def update_project(task_id):
    try:
        userID = g.user.get('userID') if g.user else None
        if not userID:
            return jsonify({"status": "error", "message": "No auth token"}), 401

        superadmin = SuperAdmin.query.filter_by(id=userID).first()
        if not superadmin:
            user = User.query.filter_by(id=userID).first()
            if not user or user.userRole.lower() != 'teamlead':
                return jsonify({"status": "error", "message": "Unauthorized"}), 403
            superadmin = SuperAdmin.query.filter_by(superId=user.superadminId).first()
            if not superadmin:
                return jsonify({"status": "error", "message": "No superadmin found"}), 404

        task = TaskManagement.query.filter_by(id=task_id, superpanelId=superadmin.superadminPanel.id).first()
        if not task:
            return jsonify({"status": "error", "message": "Task not found"}), 404

        title = request.form.get('title')
        description = request.form.get('description')
        lastDate = request.form.get('lastDate')
        status = request.form.get('status')
        links = request.form.getlist('links') or []
        files = request.form.getlist('files') or []
        emp_ids = request.form.getlist('empIDs')  # Optional for reassignment

        if title:
            task.title = title
        if description:
            task.description = description
        if lastDate:
            try:
                task.lastDate = datetime.fromisoformat(lastDate)
            except ValueError:
                return jsonify({
                    "status": "error",
                    "message": "Invalid date format for 'lastDate'. Use ISO format."
                }), 400
        if status:
            if status.lower() not in ['ongoing', 'completed', 'incomplete']:
                return jsonify({
                    "status": "error",
                    "message": "Invalid status value"
                }), 400
            task.status = status.lower()

        task.links = links
        task.files = files

        if emp_ids:
            TaskUser.query.filter_by(taskPanelId=task_id).delete()
            db.session.flush()

            for emp_id in emp_ids:
                user = User.query.filter_by(empId=emp_id).first()
                if user and user.panelData:
                    task_user = TaskUser(
                        taskPanelId=task.id,
                        userPanelId=user.panelData.id,
                        user_emp_id=user.empId,
                        usersName=getattr(user, 'userName', 'Unknown'),
                        image=getattr(user, 'profileImage', '')
                    )
                    db.session.add(task_user)

        db.session.commit()

        return jsonify({
            "status": "success",
            "message": "Task updated successfully",
            "taskId": task.id
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({
            "status": "error",
            "message": "Internal Server Error",
            "error": str(e)
        }), 500




# ====================================
#      CELEBRATION SECTION           -  admin can view upcoming birthdays of all users
# ====================================


@superAdminBP.route('/celebration', methods=['GET'])
def get_upcoming_birthdays():
    try:
        userId = g.user.get('userID') if g.user else None
        if not userId:
            return jsonify({
                "status": "error",
                "message": "Unauthorized",
            }), 400
        
        superadmin = SuperAdmin.query.filter_by(id=userId).first()
        if not superadmin:
            user = User.query.filter_by(id=userId).first()
            if not user:
                return jsonify({
                    "status": "error",
                    "message": "Unauthorized"
                }), 404
            superadmin = SuperAdmin.query.filter_by(superId=user.superadminId).first()

        allusers = superadmin.superadminPanel.allUsers
        if not allusers:
            return jsonify({
                "status": "error",
                "message": "No users yet"
            }), 404

        today = datetime.today()
        upcoming_birthdays = []

        for u in allusers:
            if u.birthday:
                birthday_this_year = u.birthday.replace(year=today.year)
                if birthday_this_year >= today:
                    upcoming_birthdays.append({
                        "id": u.id,
                        "userName": u.userName,
                        "birthday": u.birthday.strftime('%Y-%m-%d'),
                        "profileImage": u.profileImage,
                    })

        # Sort by nearest birthday
        upcoming_birthdays.sort(key=lambda x: datetime.strptime(x["birthday"], '%Y-%m-%d').replace(year=today.year))

        return jsonify({
            "status": "success",
            "message": "Fetched upcoming birthdays",
            "data": upcoming_birthdays
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({
            "status": "error",
            "message": "Internal Server Error",
            "error": str(e),
        }), 500



# ====================================
#        HOLIDAY SECTION           -  admin can set, view and change holidays 
# ====================================

@superAdminBP.route('/holiday', methods=['POST'])
def add_holidays():
    try:
        superadmin, err, status = get_authorized_superadmin()
        if err:
            return err, status

        data = request.get_json()
        country = data.get('country', 'IN')
        custom_holidays = data.get('custom_holidays', [])  # Optional list of {"date": "...", "name": "..."}

        current_year = datetime.utcnow().year
        superpanel_id = superadmin.superadminPanel.id

        existing_holiday_dates = {
            h.date for h in AdminHoliday.query.filter_by(
                superpanel=superpanel_id,
                year=current_year,
                country=country
            ).all()
        }

        new_holidays = []

        for item in custom_holidays:
            try:
                date_obj = datetime.strptime(item['date'], '%Y-%m-%d').date()
                if date_obj not in existing_holiday_dates:
                    new_holidays.append(AdminHoliday(
                        superpanel=superpanel_id,
                        date=date_obj,
                        name=item['name'],
                        country=country,
                        year=date_obj.year,
                        is_enabled=True
                    ))
            except Exception as parse_error:
                continue 

        if not custom_holidays:
            try:
                generated = holidays.CountryHoliday(country, years=current_year)
                for holiday_date, name in generated.items():
                    if holiday_date not in existing_holiday_dates:
                        new_holidays.append(AdminHoliday(
                            superpanel=superpanel_id,
                            date=holiday_date,
                            name=name,
                            country=country,
                            year=current_year,
                            is_enabled=True
                        ))
            except Exception as gen_error:
                return jsonify({
                    "status": "error",
                    "message": f"Failed to generate holidays for country '{country}'",
                    "error": str(gen_error)
                }), 400

        if not new_holidays:
            return jsonify({
                "status": "exists",
                "message": f"No new holidays to add for {current_year} in {country}"
            }), 200

        db.session.bulk_save_objects(new_holidays)
        db.session.commit()

        return jsonify({
            "status": "success",
            "message": f"{len(new_holidays)} holidays added successfully"
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({
            "status": "error",
            "message": "Internal Server Error",
            "error": str(e),
        }), 500

    
@superAdminBP.route('/holiday', methods=['GET'])
def get_holiday():
    try:
        userId = g.user.get('userID') if g.user else None
        if not userId:
            return jsonify({
                "status": "error",
                "message": "Unauthorized",
            }), 401

        superadmin = SuperAdmin.query.filter_by(id=userId).first()

        if not superadmin:
            user = User.query.filter_by(id=userId).first()
            if not user or not user.superadminId:
                return jsonify({
                    "status": "error",
                    "message": "Unauthorized"
                }), 401
            superadmin = SuperAdmin.query.filter_by(superId=user.superadminId).first()

        if not superadmin or not superadmin.superadminPanel:
            return jsonify({
                "status": "error",
                "message": "Superadmin panel not found"
            }), 404

        holidays = superadmin.superadminPanel.adminHolidays

        today = date.today()

        future_holidays = [h for h in holidays if h.date >= today]
        past_holidays = [h for h in holidays if h.date < today]

        sorted_holidays = sorted(future_holidays, key=lambda x: x.date) + \
                          sorted(past_holidays, key=lambda x: x.date, reverse=True)

        result = [{
            "id": h.id,
            "date": h.date.isoformat(),
            "name": h.name,
            "country": h.country,
            "year": h.year,
            "is_enable": h.is_enabled if h.is_enabled is not None else True,
        } for h in sorted_holidays]

        return jsonify({
            "status": "success",
            "total": len(result),
            "holidays": result
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({
            "status": "error",
            "message": "Internal Server Error",
            "error": str(e),
        }), 500


@superAdminBP.route('/holiday/<int:holiday_id>', methods=['PUT'])
def toggle_holiday(holiday_id):
    try:
        superadmin, err, status = get_authorized_superadmin()
        if err:
            return err, status

        data = request.get_json()
        new_status = data.get("is_enabled")

        holiday = AdminHoliday.query.get(holiday_id)
        if not holiday or holiday.superpanel != superadmin.superadminPanel.id:
            return jsonify({
                "status": "error",
                "message": "Holiday not found or unauthorized"
            }), 404

        if new_status is not None:
            holiday.is_enabled = bool(new_status)
        else:
            holiday.is_enabled = not holiday.is_enabled

        db.session.commit()

        return jsonify({
            "status": "success",
            "message": f"Holiday status updated to {holiday.is_enabled}",
            "holiday_id": holiday.id,
            "is_enabled": holiday.is_enabled
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({
            "status": "error",
            "message": "Internal Server Error",
            "error": str(e)
        }), 500




# ====================================
#        ASSETS SECTION           -  admin can get assets request from the user and can also edit
# ====================================

@superAdminBP.route('/assets', methods=['GET'])
def get_all_assets():
    try:
        superadmin, err, status = get_authorized_superadmin()
        if err:
            return err, status

        page = request.args.get('page', 1, type=int)
        limit = request.args.get('limit', 10, type=int)
        status_filter = request.args.get('status')

        all_users = superadmin.superadminPanel.allUsers
        if not all_users:
            return jsonify({
                "status": "error",
                "message": "No users yet.",
                "data": []
            }), 200

        asset_list = []
        for user in all_users:
            if user.panelData:
                user_assets = ProductAsset.query.filter_by(superpanel=user.panelData.id).all()
                for asset in user_assets:
                    if status_filter and asset.status != status_filter:
                        continue  # skip asset if status doesn't match
                    asset_list.append({
                        "id": asset.id,
                        "productId": asset.productId,
                        "productName": asset.productName,
                        "category": asset.category,
                        "qty": asset.qty,
                        "dateofrequest": asset.dateofrequest.strftime('%Y-%m-%d %H:%M:%S') if asset.dateofrequest else None,
                        "department": asset.department,
                        "purchaseDate": asset.purchaseDate.strftime('%Y-%m-%d') if asset.purchaseDate else None,
                        "warrantyTill": asset.warrantyTill.strftime('%Y-%m-%d') if asset.warrantyTill else None,
                        "condition": asset.condition,
                        "status": asset.status,
                        "location": asset.location,
                        "assignedTo": asset.assignedTo,
                        "username": asset.username
                    })

        total = len(asset_list)
        start = (page - 1) * limit
        end = start + limit
        paginated_assets = asset_list[start:end]

        return jsonify({
            "status": "success",
            "message": "Assets fetched successfully",
            "total_assets": total,
            "page": page,
            "total_pages": (total + limit - 1) // limit,
            "data": paginated_assets
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({
            "status": "error",
            "message": "Internal Server Error",
            "error": str(e)
        }), 500


@superAdminBP.route('/assets/<int:asset_id>', methods=['PUT'])
def update_asset_status(asset_id):
    try:
        superadmin, err, status = get_authorized_superadmin()
        if err:
            return err, status

        data = request.get_json()

        asset = ProductAsset.query.get(asset_id)

        if not asset:
            return jsonify({
                "status": "error",
                "message": "Asset not found"
            }), 404

        if 'status' in data:
            asset.status = data['status']
        if 'category' in data:
            asset.category = data['category']
        if 'dateofrequest' in data:
            asset.dateofrequest = datetime.strptime(data['dateofrequest'], '%Y-%m-%d %H:%M:%S')
        if 'purchaseDate' in data:
            asset.purchaseDate = datetime.strptime(data['purchaseDate'], '%Y-%m-%d')
        if 'warrantyTill' in data:
            asset.warrantyTill = datetime.strptime(data['warrantyTill'], '%Y-%m-%d') if data['warrantyTill'] else None
        if 'condition' in data:
            asset.condition = data['condition']
        if 'location' in data:
            asset.location = data['location']

        db.session.commit()

        if hasattr(asset, 'empId') and asset.empId:
            socketio.emit(
                'notification',
                {
                    'title': '🛠️ Asset Updated',
                    'message': f'Your asset request has been updated. Status: {asset.status}',
                    'type': 'asset',
                    'assetId': asset.id
                },
                room=asset.empId
            )

        return jsonify({
            "status": "success",
            "message": "Asset updated successfully"
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({
            "status": "error",
            "message": "Internal Server Error",
            "error": str(e)
        }), 500




# ====================================
#      DEPARTMENT SECTION            - admin will create department for here only
# ====================================


@superAdminBP.route('/department', methods=['POST'])
def add_department():
    try:
        data = request.get_json()
        if not data or not data.get('name'):
            return jsonify({
                "status": "error",
                "message": "Department name is required"
            }), 400

        superadmin, err, status = get_authorized_superadmin()
        if err:
            return err, status

        existing_department = AdminDepartment.query.filter_by(
            name=data['name'].strip(),
            superpanel=superadmin.superadminPanel.id
        ).first()

        if existing_department:
            return jsonify({
                "status": "error",
                "message": "Department with this name already exists"
            }), 409

        department = AdminDepartment(
            superpanel=superadmin.superadminPanel.id,
            name=data['name'].strip()
        )

        db.session.add(department)
        db.session.commit()

        return jsonify({
            "status": "success",
            "message": "Department added successfully",
            "department": {
                "id": department.id,
                "name": department.name
            }
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({
            "status": "error",
            "message": "Internal Server Error",
            "error": str(e)
        }), 500


@superAdminBP.route('/department/<int:id>', methods=['DELETE'])
def delete_department(id):
    try:
        superadmin, err, status = get_authorized_superadmin()
        if err:
            return err, status

        department = AdminDepartment.query.filter_by(id=id, superpanel=superadmin.superadminPanel.id).first()
        if not department:
            return jsonify({
                "status": "error",
                "message": "Department not found"
            }), 404

        db.session.delete(department)
        db.session.commit()

        return jsonify({
            "status": "success",
            "message": "Department deleted successfully"
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({
            "status": "error",
            "message": "Internal Server Error",
            "error": str(e)
        }), 500


@superAdminBP.route('/department', methods=['GET'])
def get_departments_with_users():
    try:
        superadmin, err, status = get_authorized_superadmin()
        if err:
            return err, status

        departments = AdminDepartment.query.filter_by(superpanel=superadmin.superadminPanel.id).all()
        if not departments:
            return jsonify({
                "status": "error",
                "message": "No departments yet"
            }), 200

        all_users = superadmin.superadminPanel.allUsers or []

        department_list = []
        for dept in departments:
            dept_users = [
                {
                    "name": u.userName,
                    "profileImage": u.profileImage,
                    "department": u.department
                }
                for u in all_users if u.department and u.department.lower() == dept.name.lower()
            ]

            department_list.append({
                "id": dept.id,
                "name": dept.name,
                "users": dept_users
            })

        return jsonify({
            "status": "success",
            "message": "Fetched departments with users",
            "data": department_list
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({
            "status": "error",
            "message": "Internal Server Error",
            "error": str(e),
        }), 500




# ====================================
#      SALARY SECTION           -  admin will get calculated salary of all users
# ====================================


@superAdminBP.route('/salary', methods=['GET'])
def get_all_user_admin_data():
    try:
        superadmin, err, status = get_authorized_superadmin(required_section="dashboard", required_permissions="view")
        if err:
            return err, status

        today = datetime.utcnow().date()
        month_start = today.replace(day=1)
        month_end = today.replace(day=31) if today.month == 12 else (today.replace(month=today.month + 1, day=1) - timedelta(days=1))

        # --- Query Parameters ---
        search_name = request.args.get('name', '').strip().lower()
        search_department = request.args.get('department', '').strip().lower()
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 10))
        offset = (page - 1) * limit

        # --- Base Query ---
        user_query = User.query.filter_by(superadminId=superadmin.superId)
        if search_name:
            user_query = user_query.filter(func.lower(User.userName).like(f"%{search_name}%"))

        # --- Total Before Pagination ---
        total_users = user_query.count()

        # --- Apply Pagination ---
        users = user_query.offset(offset).limit(limit).all()
        user_data_list = []

        for user in users:
            panel_data = user.panelData

            # --- Skip if department doesn't match ---
            if search_department and (
                not panel_data or not panel_data.userJobInfo or
                panel_data.userJobInfo[0].department.lower() != search_department
            ):
                continue

            # --- Punch Info ---
            punch_count = 0
            total_halfday = 0
            total_late = 0
            if panel_data:
                punch_query = db.session.query(PunchData).filter(
                    PunchData.panelData == panel_data.id,
                    PunchData.login >= month_start,
                    PunchData.login <= month_end
                )
                punch_count = punch_query.count()
                for status in punch_query.with_entities(PunchData.status).all():
                    if status[0] == 'halfday':
                        total_halfday += 1
                    elif status[0] == 'late':
                        total_late += 1

            # --- Leave Info ---
            paid_days = 0
            unpaid_days = 0
            leave_count = 0
            if panel_data:
                leaves = db.session.query(UserLeave).filter(
                    UserLeave.panelData == panel_data.id,
                    UserLeave.status == 'approved',
                    UserLeave.leavefrom >= month_start,
                    UserLeave.leavefrom <= month_end
                ).all()
                leave_count = len(leaves)
                for leave in leaves:
                    unpaid = leave.unpaidDays or 0
                    unpaid_days += unpaid
                    paid_days += max((leave.days or 0) - unpaid, 0)

            # --- Job & Salary Info ---
            job_info = {
                "department": panel_data.userJobInfo[0].department if panel_data and panel_data.userJobInfo else None,
                # "designation": panel_data.userJobInfo[0].designation if panel_data and panel_data.userJobInfo else None,
                # "joiningDate": panel_data.userJobInfo[0].joiningDate.isoformat() if panel_data and panel_data.userJobInfo and panel_data.userJobInfo[0].joiningDate else None
            }

            user_data_list.append({
                "empId": user.empId,
                "name": user.userName,
                "email": user.email,
                "role": user.userRole,
                "basic_salary": user.currentSalary,
                "present": punch_count,
                "halfday": total_halfday,
                "late": total_late,
                "leave_summary": {
                    "absent": leave_count,
                    "paid_days": paid_days,
                    "unpaid_days": unpaid_days
                },
                "jobInfo": job_info
            })

        # --- Admin Policies ---
        admin_panel = superadmin.superadminPanel

        bonus_policy = [{
            "bonus_name": b.bonus_name,
            "amount": b.amount,
            "bonus_method": b.bonus_method,
            "apply": b.apply,
            "employeement_type": b.employeement_type,
            "department_type": b.department_type
        } for b in admin_panel.adminBonusPolicy]

        payroll_policy = [{
            "policyname": p.policyname,
            "calculation_method": p.calculation_method,
            "overtimePolicy": p.overtimePolicy,
            "perhour": p.perhour,
            "pfDeduction": p.pfDeduction,
            "salaryHoldCondition": p.salaryHoldCondition,
            "disbursement": p.disbursement.isoformat() if p.disbursement else None,
            "employeementType": p.employeementType,
            "departmentType": p.departmentType
        } for p in admin_panel.adminPayrollPolicy]

        leave_policy = [{
            "leaveName": l.leaveName,
            "leaveType": l.leaveType,
            "probation": l.probation,
            "lapse_policy": l.lapse_policy,
            "calculationType": l.calculationType,
            "day_type": l.day_type,
            "encashment": l.encashment,
            "carryforward": l.carryforward,
            "max_leave_once": l.max_leave_once,
            "max_leave_year": l.max_leave_year,
            "monthly_leave_limit": l.monthly_leave_limit
        } for l in admin_panel.adminLeave]

        shift = ShiftTimeManagement.query.filter_by(
            superpanel=admin_panel.id,
            shiftStatus=True
        ).first()

        total_working_days = 0
        working_days_list = shift.workingDays if shift and shift.workingDays else []
        saturday_condition = shift.saturdayCondition if shift and shift.saturdayCondition else None

        if working_days_list:
            working_days_set = set(day.lower() for day in working_days_list)
            month_range = calendar.monthrange(today.year, today.month)[1]
            for day in range(1, month_range + 1):
                date = datetime(today.year, today.month, day).date()
                weekday = date.strftime("%A").lower()
                if weekday == 'saturday':
                    if saturday_condition:
                        week_no = (day - 1) // 7 + 1
                        if (
                            (saturday_condition == 'All Saturdays Working') or
                            (saturday_condition == 'First & Third Saturdays Working' and week_no in [1, 3]) or
                            (saturday_condition == 'Second & Fourth Saturdays Working' and week_no in [2, 4]) or
                            (saturday_condition == 'Only First Saturday Working' and week_no == 1)
                        ):
                            total_working_days += 1
                elif weekday in working_days_set:
                    total_working_days += 1

        return jsonify({
            "status": "success",
            "data": {
                "users": user_data_list,
                "pagination": {
                    "page": page,
                    "limit": limit,
                    "total": total_users,
                    "totalPages": (total_users + limit - 1) // limit
                },
                "admin": {
                    "bonus_policy": bonus_policy,
                    "payroll_policy": payroll_policy,
                    "leave_policy": leave_policy
                },
                "shift_policy": {
                    "workingDays": working_days_list,
                    "saturdayCondition": saturday_condition,
                    "totalWorkingDaysThisMonth": total_working_days
                }
            }
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({
            "status": "error",
            "message": "Failed to fetch user-admin data",
            "error": str(e)
        }), 500


@superAdminBP.route('/salary', methods=['POST'])
def post_user_salary():
    data = request.form

    required_fields = [
        'empId', 'present', 'absent', 'basicSalary',
        'deductions', 'finalPay', 'mode', 'status', 'approvedLeaves'
    ]

    if not all(field in data for field in required_fields):
        return jsonify({'status': 'error', 'message': 'Missing required salary fields'}), 400

    try:
        superadmin, err, status = get_authorized_superadmin(required_section="salary", required_permissions="edit")
        if err:
            return err, status

        emp_id = data.get('empId')
        user = User.query.filter_by(empId=emp_id, superadminId=superadmin.superId).first()
        if not user:
            return jsonify({'status': 'error', 'message': 'User with this empId not found'}), 404

        panel_data = user.panelData
        if not panel_data:
            return jsonify({'status': 'error', 'message': 'UserPanelData not found'}), 404

        onhold = data.get('onhold', 'false').lower() == 'true'
        onhold_reason = data.get('onhold_reason') or None
        bonusamount = data.get('bonus') or None
        bonusreason = data.get('bonus_reason') or None
        payslip = data.get('payslip') or None

        salary_entry = UserSalaryDetails(
            panelDataID=panel_data.id,
            empId=emp_id,
            present=data.get('present'),
            absent=data.get('absent'),
            basicSalary=data.get('basicSalary'),
            deductions=data.get('deductions'),
            finalPay=data.get('finalPay'),
            mode=data.get('mode'),
            status=data.get('status'),
            payslip=payslip,
            approvedLeaves=data.get('approvedLeaves'),
            onhold=onhold,
            onhold_reason=onhold_reason,
            bonus=bonusamount,
            bonus_reason=bonusreason
        )

        db.session.add(salary_entry)
        db.session.commit()

        return jsonify({'status': 'success', 'message': 'Salary data saved successfully'}), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({
            'status': 'error',
            'message': 'Internal Server Error',
            'error': str(e)
        }), 500


@superAdminBP.route('/salaryrecords', methods=['GET'])
def get_user_salaries():
    try:
        superadmin, err, status = get_authorized_superadmin(required_section="salary", required_permissions="view")
        if err:
            return err, status

        emp_id = request.args.get('empId')
        month = request.args.get('month')  # 1-12
        year = request.args.get('year')    # YYYY
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 10))
        start = (page - 1) * limit

        query = UserSalaryDetails.query.join(UserPanelData).join(User).filter(
            User.superadminId == superadmin.superId
        )

        if emp_id:
            query = query.filter(UserSalaryDetails.empId == emp_id)

        if month and year:
            try:
                month = int(month)
                year = int(year)
                month_start = datetime(year, month, 1)
                if month == 12:
                    month_end = datetime(year + 1, 1, 1)
                else:
                    month_end = datetime(year, month + 1, 1)

                query = query.filter(
                    UserSalaryDetails.createdAt >= month_start,
                    UserSalaryDetails.createdAt < month_end
                )
            except ValueError:
                return jsonify({'status': 'error', 'message': 'Invalid month or year format'}), 400

        total_records = query.count()
        salary_data = query.order_by(UserSalaryDetails.createdAt.desc()).offset(start).limit(limit).all()

        results = []
        for salary in salary_data:
            results.append({
                "empId": salary.empId,
                "present": salary.present,
                "absent": salary.absent,
                "approvedLeaves": salary.approvedLeaves,
                "basicSalary": salary.basicSalary,
                "deductions": salary.deductions,
                "finalPay": salary.finalPay,
                "mode": salary.mode,
                "status": salary.status,
                "payslip": salary.payslip,
                "onhold": salary.onhold,
                "onhold_reason": salary.onhold_reason,
                "createdAt": salary.createdAt.strftime("%Y-%m-%d")
            })

        return jsonify({
            "status": "success",
            "data": {
                "salaries": results,
                "pagination": {
                    "page": page,
                    "limit": limit,
                    "total": total_records,
                    "pages": (total_records + limit - 1) // limit
                }
            }
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({
            "status": "error",
            "message": "Failed to fetch salary records",
            "error": str(e)
        }), 500




# ====================================
#      PROMOTION SECTION         - admin will set promotion of particular users  
# ====================================

@superAdminBP.route('/promotion/<int:user_id>', methods=['POST'])
def promote_user(user_id):
    try:
        superadmin, err, status = get_authorized_superadmin(required_section="employee", required_permissions="edit")
        if err:
            return err, status

        data = request.get_json()
        if not data or 'new_designation' not in data:
            return jsonify({
                "status": "error",
                "message": "Missing 'new_designation' in request body"
            }), 400

        user = User.query.filter_by(id=user_id, superadminId=superadmin.superId).first()
        if not user:
            return jsonify({"status": "error", "message": "User not found"}), 404

        panel = user.panelData
        if not panel:
            return jsonify({"status": "error", "message": "User panel data not found"}), 404

        job_info = user.department

        previous_department = job_info.department
        new_department = data.get("new_department", previous_department)
        new_designation = data["new_designation"]
        description = data.get("description")

        promotion = UserPromotion(
            id=int(datetime.utcnow().timestamp()),
            empId=user.empId,
            new_designation=new_designation,
            previous_department=previous_department,
            new_department=new_department,
            description=description,
            userpanel=panel.id
        )

        db.session.add(promotion)
        db.session.commit()

        socketio.emit(
            'notification',
            {
                'title': '🎉 Promotion Update',
                'message': f"You have been promoted to {new_designation}",
                'type': 'promotion',
                'empId': user.empId
            },
            room=user.empId
        )

        return jsonify({
            "status": "success",
            "message": f"User {user.empId} promoted to {new_designation}",
            "promotion_id": promotion.id
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({
            "status": "error",
            "message": "Internal Server Error",
            "error": str(e)
        }), 500


@superAdminBP.route('/promotion/<int:promotion_id>', methods=['DELETE'])
def delete_promotion(promotion_id):
    try:
        superadmin, err, status = get_authorized_superadmin(required_section="employee", required_permissions="edit")
        if err:
            return err, status

        promotion = UserPromotion.query.get(promotion_id)
        if not promotion:
            return jsonify({
                "status": "error",
                "message": "Promotion record not found"
            }), 404

        user = User.query.filter_by(empId=promotion.empId, superadminId=superadmin.superId).first()
        if not user:
            return jsonify({
                "status": "error",
                "message": "Unauthorized to delete this promotion"
            }), 403

        db.session.delete(promotion)
        db.session.commit()

        return jsonify({
            "status": "success",
            "message": f"Promotion record {promotion_id} deleted successfully"
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({
            "status": "error",
            "message": "Internal Server Error",
            "error": str(e)
        }), 500




# ====================================
#      ADMIN MESSAGE SECTION         - admin will chat with users  
# ====================================


@superAdminBP.route('/message', methods=['POST'])
def admin_send_message():
    try:
        superadminID = g.user.get('userID') if g.user else None
        if not superadminID or g.user.get('userType') != 'superadmin':
            return jsonify({"status": "error", "message": "Unauthorized"}), 403

        superadmin = SuperAdmin.query.filter_by(id=superadminID).first()
        if not superadmin:
            return jsonify({"status": "error", "message": "Admin not found"}), 404

        receiver_id = request.form.get('recieverID')
        message_text = request.form.get('message')
        uploaded_file = request.files.get('file')  # optional

        if not receiver_id:
            return jsonify({"status": "error", "message": "Receiver ID required"}), 400
        if not message_text and not uploaded_file:
            return jsonify({"status": "error", "message": "Message or file required"}), 400

        user = User.query.filter_by(id=receiver_id).first()
        if not user:
            return jsonify({"status": "error", "message": "User not found"}), 404

        file_url = None
        message_type = 'text'

        if uploaded_file:
            filename = secure_filename(uploaded_file.filename)
            mimetype = uploaded_file.mimetype
            folder_path = os.path.join('static', 'uploads', 'chat_files')
            os.makedirs(folder_path, exist_ok=True)
            filepath = os.path.join(folder_path, filename)
            uploaded_file.save(filepath)
            file_url = filepath

            if mimetype.startswith("image/"):
                message_type = 'image' if not message_text else 'text_image'
            else:
                message_type = 'file' if not message_text else 'text_file'

        message = UserChat(
            panelData=user.panelData.id,
            senderID=superadmin.empId,
            recieverID=user.empId,
            message=message_text if message_text else None,
            image_url=file_url,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )

        db.session.add(message)
        db.session.commit()

        socketio.emit('receive_message', {
            'senderID': superadmin.empId,
            'recieverID': user.empId,
            'message': message_text,
            'file_url': file_url,
            'message_type': message_type,
            'timestamp': str(message.created_at)
        }, room=receiver_id)

        socketio.emit('message_sent', {'status': 'success'}, room=superadmin.empId)

        return jsonify({"status": "success", "message": "Message sent"}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({
            "status": "error",
            "message": "Internal Server Error",
            "error": str(e)
        }), 500


@superAdminBP.route('/message/<string:with_empId>', methods=['GET'])
def get_admin_chat(with_empId):
    try:
        superadminID = g.user.get('userID') if g.user else None
        if not superadminID or g.user.get('userType') != 'superadmin':
            return jsonify({"status": "error", "message": "Unauthorized"}), 403

        superadmin = SuperAdmin.query.filter_by(id=superadminID).first()
        if not superadmin or not superadmin.companyEmail:
            return jsonify({"status": "error", "message": "Admin not found"}), 404

        sender_empId = superadmin.companyEmail

        chats = UserChat.query.filter(
            ((UserChat.senderID == sender_empId) & (UserChat.recieverID == with_empId)) |
            ((UserChat.senderID == with_empId) & (UserChat.recieverID == sender_empId))
        ).order_by(UserChat.created_at.asc()).all()

        messages = []
        for chat in chats:
            message_data = {
                "id": chat.id,
                "senderID": chat.senderID,
                "receiverID": chat.recieverID,
                "message": chat.message,
                "image_url": None,
                "message_type": "image" if chat.image_url and chat.image_url.lower().endswith(('.jpg', '.jpeg', '.png')) else (
                    "file" if chat.image_url else "text"
                ),
                "created_at": chat.created_at.isoformat()
            }

            if chat.image_url:
                message_data["image_url"] = url_for(
                    'static', filename=chat.image_url.replace('static/', ''), _external=True
                )

            messages.append(message_data)

        return jsonify({"status": "success", "messages": messages}), 200

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": "Internal Server Error",
            "error": str(e)
        }), 500




# ====================================
#      ADMIN MESSAGE SECTION         - admin set location of office  
# ====================================


@superAdminBP.route('/location', methods=['POST'])
def set_admin_location():
    try:
        superadmin, err, status = get_authorized_superadmin()
        if err:
            return err, status

        data = request.get_json()
        if not data:
            return jsonify({
                "status": "error",
                "message": "No data provided"
            }), 400

        latitude = data.get('latitude')
        longitude = data.get('longitude')

        if not latitude or not longitude:
            return jsonify({
                "status": "error",
                "message": "Latitude and longitude are required"
            }), 400

        # Check if location already exists for this superpanel
        existing_location = AdminLocation.query.filter_by(superpanel=superadmin.superadminPanel.id).first()

        if existing_location:
            existing_location.latitude = latitude
            existing_location.longitude = longitude
            message = "Location updated successfully"
        else:
            new_location = AdminLocation(
                superpanel=superadmin.superadminPanel.id,
                latitude=latitude,
                longitude=longitude
            )
            db.session.add(new_location)
            message = "Location saved successfully"

        db.session.commit()

        return jsonify({
            "status": "success",
            "message": message,
            "data": {
                "latitude": latitude,
                "longitude": longitude
            }
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({
            "status": "error",
            "message": "Failed to save location",
            "error": str(e)
        }), 500


@superAdminBP.route('/location', methods=['GET'])
def get_admin_location():
    try:
        superadmin, err, status = get_authorized_superadmin()
        if err:
            return err, status

        location = AdminLocation.query.filter_by(superpanel=superadmin.superadminPanel.id).first()

        if not location:
            return jsonify({
                "status": "error",
                "message": "Location not set"
            }), 404

        return jsonify({
            "status": "success",
            "message": "Location fetched successfully",
            "data": {
                "latitude": location.latitude,
                "longitude": location.longitude
            }
        }), 200

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": "Failed to fetch location",
            "error": str(e)
        }), 500
