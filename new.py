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
            print(f"Checking emp_id: {emp_id}")
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

        tasks = TaskManagement.query.options(
            joinedload(TaskManagement.users),
            joinedload(TaskManagement.comments)
        ).filter_by(
            superpanelId=superadmin.superadminPanel.id
        ).order_by(TaskManagement.assignedAt.desc()).all()

        grouped_tasks = {
            "completed": [],
            "ongoing": [],
            "incomplete": []
        }

        for task in tasks:
            assigned_users = []
            all_completed = True
            any_assigned = False

            for user in task.users:
                any_assigned = True
                assigned_users.append({
                    "userPanelId": user.userPanelId,
                    "empId": user.user_emp_id,
                    "userName": user.user_userName,
                    "image": user.image,
                    "isCompleted": user.is_completed
                })
                if not user.is_completed:
                    all_completed = False

            if all_completed and any_assigned:
                task_status = "completed"
            elif not all_completed and task.lastDate and datetime.utcnow() > task.lastDate:
                task_status = "incomplete"
            else:
                task_status = "ongoing"

            comments = [{
                "id": c.id,
                "userId": c.userId,
                "username": c.username,
                "comment": c.comments,
                "timestamp": c.timestamp.isoformat() if hasattr(c, "timestamp") and c.timestamp else None
            } for c in task.comments]

            task_data = {
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
            }

            grouped_tasks[task_status].append(task_data)

        return jsonify({
            "status": "success",
            "tasks": grouped_tasks
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


@superAdminBP.route('/salary', methods=['GET'])
def get_all_user_admin_data():
    try:
        superadmin, err, status = get_authorized_superadmin(required_section="dashboard", required_permissions="view")
        if err:
            return err, status

        # Get month and year from query params (fallback to current)
        query_month = request.args.get('month', type=int)
        query_year = request.args.get('year', type=int)

        today = datetime.utcnow().date()
        month = query_month if query_month else today.month
        year = query_year if query_year else today.year

        month_start = datetime(year, month, 1).date()
        if month == 12:
            month_end = datetime(year, 12, 31).date()
        else:
            month_end = (datetime(year, month + 1, 1) - timedelta(days=1)).date()

        users = User.query.filter_by(superadminId=superadmin.superId).all()
        user_data_list = []

        for user in users:
            panel_data = user.panelData

            # --- Punch Count ---
            punch_count = 0
            if panel_data:
                punch_count = db.session.query(PunchData).filter(
                    PunchData.panelData == panel_data.id,
                    PunchData.login >= month_start,
                    PunchData.login <= month_end
                ).count()

            # --- Leave Summary ---
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

            # --- Job Info ---
            job_info = {
                "department": panel_data.userJobInfo[0].department if panel_data and panel_data.userJobInfo else None,
                "designation": panel_data.userJobInfo[0].designation if panel_data and panel_data.userJobInfo else None,
                "joiningDate": panel_data.userJobInfo[0].joiningDate.isoformat() if panel_data and panel_data.userJobInfo and panel_data.userJobInfo[0].joiningDate else None
            }

            # --- Basic Salary ---
            basic_salary = panel_data.userSalaryDetails[0].basic_salary if panel_data and panel_data.userSalaryDetails else None

            user_data_list.append({
                "empId": user.empId,
                "name": user.userName,
                "email": user.email,
                "role": user.userRole,
                "punch_count": punch_count,
                "leave_summary": {
                    "total_leaves": leave_count,
                    "paid_days": paid_days,
                    "unpaid_days": unpaid_days
                },
                "basic_salary": basic_salary,
                "jobInfo": job_info
            })

        # --- Admin-Side Info ---
        admin_panel = superadmin.superadminPanel

        # Bonus Policy Fix
        bonus_policy = [{
            "bonus_name": b.bonus_name,
            "bonus_method": b.bonus_method,
            "amount": b.amount,
            "apply": b.apply,
            "employeement_type": b.employeement_type,
            "department_type": b.department_type
        } for b in admin_panel.adminBonusPolicy]

        # Payroll Policy Fix
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

        # Leave Policy Fix
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

        return jsonify({
            "status": "success",
            "data": {
                "users": user_data_list,
                "admin": {
                    "bonus_policy": bonus_policy,
                    "payroll_policy": payroll_policy,
                    "leave_policy": leave_policy
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


@superAdminBP.route('/salary', methods=['GET'])
def get_all_user_admin_data():
    try:
        superadmin, err, status = get_authorized_superadmin(required_section="dashboard", required_permissions="view")
        if err:
            return err, status

        today = datetime.utcnow().date()
        month_start = today.replace(day=1)
        if today.month == 12:
            month_end = today.replace(day=31)
        else:
            month_end = (today.replace(month=today.month + 1, day=1) - timedelta(days=1))

        users = User.query.filter_by(superadminId=superadmin.superId).all()
        user_data_list = []

        for user in users:
            panel_data = user.panelData

            # --- Punch count this month ---
            punch_count = 0
            if panel_data:
                punch_count = db.session.query(PunchData).filter(
                    PunchData.panelData == panel_data.id,
                    PunchData.login >= month_start,
                    PunchData.login <= month_end
                ).count()

            # --- Leave details this month ---
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

            # --- Job info ---
            job_info = {
                "department": panel_data.userJobInfo[0].department if panel_data and panel_data.userJobInfo else None,
                "designation": panel_data.userJobInfo[0].designation if panel_data and panel_data.userJobInfo else None,
                "joiningDate": panel_data.userJobInfo[0].joiningDate.isoformat() if panel_data and panel_data.userJobInfo and panel_data.userJobInfo[0].joiningDate else None
            }

            # --- Basic Salary ---
            basic_salary = panel_data.userSalaryDetails[0].basic_salary if panel_data and panel_data.userSalaryDetails else None

            user_data_list.append({
                "empId": user.empId,
                "name": user.userName,
                "email": user.email,
                "role": user.userRole, 
                "basic_salary": user.currentSalary,
                "present": punch_count,
                "leave_summary": {
                    "absent": leave_count,
                    "paid_days": paid_days,
                    "unpaid_days": unpaid_days
                },
                "jobInfo": job_info
            })

        # --- Admin-Side Info ---
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
            superpanel = admin_panel.id,
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
                        if(
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
                "admin": {
                    "bonus_policy": bonus_policy,
                    "payroll_policy": payroll_policy,
                    "leave_policy": leave_policy
                },
                "shift_policy" : {
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
    

@superAdminBP.route('/message', methods=['POST'])
def admin_send_message():
    try:
        superadmin, err, status = get_authorized_superadmin(required_section="chat", required_permissions="edit")
        if err:
            return err, status

        receiver_id = request.form.get('recieverID')
        department_name = request.form.get('department')  # optional
        message_text = request.form.get('message')
        uploaded_file = request.files.get('file')

        if not receiver_id and not department_name:
            return jsonify({"status": "error", "message": "Receiver ID or Department is required"}), 400
        if not message_text and not uploaded_file:
            return jsonify({"status": "error", "message": "Message or file required"}), 400

        # File handling
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

        # Determine recipients
        if department_name:
            users = User.query.filter_by(superadminId=superadmin.superId, department=department_name).all()
            if not users:
                return jsonify({"status": "error", "message": "No users found in this department"}), 404
        else:
            user = User.query.filter_by(id=receiver_id).first()
            if not user:
                return jsonify({"status": "error", "message": "User not found"}), 404
            users = [user]

        # Send to all selected users
        for user in users:
            message = UserChat(
                panelData=user.panelData.id,
                senderID=superadmin.superId,
                recieverID=user.empId,
                message=message_text if message_text else None,
                image_url=file_url,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            db.session.add(message)
            db.session.flush()  # get created_at

            socketio.emit('receive_message', {
                'senderID': superadmin.superId,
                'recieverID': user.empId,
                'message': message_text,
                'file_url': file_url,
                'message_type': message_type,
                'timestamp': str(message.created_at)
            }, room=user.id)  # emit to individual user room

        db.session.commit()

        socketio.emit('message_sent', {'status': 'success'}, room=str(superadmin.superId))
        return jsonify({"status": "success", "message": "Message sent successfully"}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({
            "status": "error",
            "message": "Internal Server Error",
            "error": str(e)
        }), 500
