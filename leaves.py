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