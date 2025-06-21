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
