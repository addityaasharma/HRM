@superAdminBP.route('/project', methods=['POST'])
def add_Project():
    try:
        superadmin, err, status = get_authorized_superadmin()
        if err:
            return err, status

        title = request.form.get('title')
        description = request.form.get('description')
        lastDate = request.form.get('lastDate')

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
            links=links,
            files=files
        )
        db.session.add(new_task)
        db.session.flush()

        for emp_id in emp_ids:
            user = User.query.filter_by(empId=emp_id).first()
            if user and user.panelData:
                user_panel = user.panelData
                task_user = TaskUser(
                    taskPanelId=new_task.id,
                    userPanelId=user_panel.id,
                    user_emp_id=user.empId,
                    usersName=getattr(user, 'userName', 'Unknown'),
                    image=getattr(user, 'profileImage', '')
                )
                db.session.add(task_user)
            else:
                print(f"⚠️ No user found for emp_id: {emp_id}")

        db.session.commit()

        return jsonify({
            "status": "success",
            "message": "Project and task assignments added successfully",
            "taskId": new_task.id
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
            comments = []
            for comment in task.comments:
                comments.append({
                    "id": comment.id,
                    "userId": comment.userId,
                    "username": comment.username,
                    "comment": comment.comments,
                    "timestamp": comment.timestamp.isoformat() if hasattr(comment, "timestamp") and comment.timestamp else None
                })

            assigned_users = []
            for user in task.users:
                assigned_users.append({
                    "userPanelId": user.userPanelId,
                    "empId": user.user_emp_id,
                    "userName": user.user_userName,
                    "image": user.image,
                    "isCompleted": user.is_completed
                })

            task_list.append({
                "id": task.id,
                "title": task.title,
                "description": task.description,
                "assignedAt": task.assignedAt.isoformat() if task.assignedAt else None,
                "lastDate": task.lastDate.isoformat() if task.lastDate else None,
                "links": task.links,
                "files": task.files,
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
