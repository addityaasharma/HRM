@superAdminBP.route('/announcement', methods=['GET'])
def get_announcement():
    try:
        userID = g.user.get('userID') if g.user else None
        if not userID:
            return jsonify({"status": "error", "message": "No user or auth token provided"}), 404

        superadmin = SuperAdmin.query.filter_by(id=userID).first()
        if not superadmin:
            return jsonify({"status": "error", "message": "SuperAdmin not found"}), 404

        allAnnouncement = superadmin.superadminPanel.adminAnnouncement

        filtered_announcements = [
            ann for ann in allAnnouncement
            if ann.is_published and (not ann.scheduled_time or ann.scheduled_time <= datetime.utcnow())
        ]

        page = request.args.get('page', 1, type=int)
        limit = request.args.get('limit', 10, type=int)
        start = (page - 1) * limit
        end = start + limit
        paginated_announcements = filtered_announcements[start:end]

        result = []
        for ann in paginated_announcements:
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
            "message": "Fetched published announcements",
            "data": result,
            "pagination": {
                "page": page,
                "per_page": limit,
                "total_items": len(filtered_announcements),
                "total_pages": (len(filtered_announcements) + limit - 1) // limit
            }
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({
            "status": "error",
            "message": "Internal Server Error",
            "error": str(e)
        }), 500
