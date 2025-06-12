from models import SuperAdmin, SuperAdminPanel, db, PunchData, User, UserTicket
from werkzeug.security import generate_password_hash, check_password_hash
from flask import Blueprint, request, jsonify, g
import datetime, random, string, re, math
from middleware import create_tokens
from sqlalchemy import desc

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


@superAdminBP.route('/edit-punchdetails/<int:punchId>',methods=['PUT'])
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


@superAdminBP.route('/all-users', methods = ['GET'])
def allUsers():
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
                'message': 'No admin found with this id'
            }), 400

        if superadmin.is_super_admin is not True:
            user = User.query.filter_by(id=userID).first()
            if user.userRole.lower() != 'hr':
                return jsonify({
                'status': 'error',
                'message': 'Unauthorized: you dont have access to this route'
            }), 403

        
        superadminpanel = superadmin.superadminPanel
        if not superadminpanel:
            return jsonify({
                'status': 'error',
                'message': "No admin panel found with this user"
            }), 400

        all_users_query = superadminpanel.allUsers

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
                'userName': user.userName,
                'email': user.email,
                'empId': user.empId,
                'department': user.department,
                'source_of_hire': user.sourceOfHire,
                'PAN': user.panNumber,
                'UAN': user.uanNumber,
                'joiningDate': user.joiningDate,
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
        return jsonify({
            'status': 'error',
            'message': "Internal server error",
            'error': str(e)
        }), 500


@superAdminBP.route('/edit_user/<int:userId>',methods=['PUT'])
def edit_user(userId):
    data=request.get_json()
    if not data:
        return jsonify({
            "status" : "error",
            "message" : "Please provide data"
        }), 404
    
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
            if not user:
                return jsonify({
                    "status" : "error",
                    "message" : "No user or admin found"
                }), 400
            
            if user.userRole.lower() != "hr":
                return jsonify({
                    "status" : "error",
                    "message" : "You are not allowed to edit this role"
                }), 409
        
        user = User.query.filter_by(id=userId).first()
        if not user:
            return jsonify({
                "status" : "error",
                "message" : "No user found with this Id"
            }), 409
        
        updatable_fields = [
            'profileImage', 'userName', 'gender', 'number','userRole',
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
            'status' : "error",
            "message" : "Internal Server Error",
            "error" : str(e)
        }), 500


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


@superAdminBP.route('/all_leaves', methods=['GET'])
def user_leaves():
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
                return jsonify({"status": "error", "message": "You are not allowed to manage this."}), 400

        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 10))
        status = request.args.get('status') 
        department = request.args.get('department')

        query = User.query.filter_by(superadminId=superadmin.id)

        if department:
            query = query.filter(User.department.ilike(f"%{department}%"))

        total_users = query.count()
        users = query.offset((page - 1) * limit).limit(limit).all()

        results = []

        for user in users:
            if user.panelData and user.panelData.userLeaveData:
                filtered_leaves = [
                    {
                        "leaveId": leave.id,
                        "type": leave.leavetype,
                        "from": leave.leavefrom,
                        "to": leave.leaveto,
                        "status": leave.status,
                        "reason": leave.reason,
                        "empId": leave.empId,
                        "email": leave.email,
                        "day": leave.day,
                        "month": leave.month
                    }
                    for leave in user.panelData.userLeaveData
                    if not status or leave.status.lower() == status.lower()
                ]
                if filtered_leaves:
                    results.append({
                        "userId": user.id,
                        "userName": user.userName,
                        "department": user.department,
                        "leaves": filtered_leaves
                    })

        if not results:
            return jsonify({
                "status": "error",
                "message": "No leave data found for given filters"
            }), 409

        return jsonify({
            "status": "success",
            "message": "Leave data fetched successfully",
            "page": page,
            "limit": limit,
            "totalUsers": total_users,
            "data": results
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({
            "status": "error",
            "message": "Internal Server Error",
            "error": str(e)
        }), 500