from datetime import datetime, time
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.dialects.mysql import ENUM
from sqlalchemy.dialects.mysql import JSON


db = SQLAlchemy()

class Master(db.Model):
    __tablename__ = 'master'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(100), nullable=False)
    company_email = db.Column(db.String(120), nullable=False)
    company_password = db.Column(db.String(120), nullable=False)
    masteradminPanel = db.relationship('MasterPanel',backref='master', uselist=False, lazy=True)


class MasterPanel(db.Model):
    __tablename__ = 'masteradminpanel'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    masterid = db.Column(db.Integer, db.ForeignKey('master.id'), nullable=False)
    allSuperAdmins = db.relationship('SuperAdmin', backref='masterpanel',lazy=True)

# ====================================
#            SUPERADMIN SECTION
# ====================================

class SuperAdmin(db.Model):
    __tablename__ = 'superadmin'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    superId = db.Column(db.String(120), nullable=False)
    companyName = db.Column(db.String(100), nullable=False)
    companyEmail = db.Column(db.String(120), nullable=False)
    company_password = db.Column(db.String(250), nullable=False)
    company_image =db.Column(db.String(255))

    #details
    company_type = db.Column(db.String(250))
    company_website = db.Column(db.String(250))
    company_estabilish = db.Column(db.DateTime)
    company_years = db.Column(db.Integer)
    is_super_admin = db.Column(db.Boolean)
    expiry_date = db.Column(db.DateTime, nullable=True)
    master_id = db.Column(db.Integer, db.ForeignKey('masteradminpanel.id'), nullable=False)
    superadminPanel = db.relationship('SuperAdminPanel', backref='superadmin', uselist=False, lazy=True)  #superadmin panel


class SuperAdminPanel(db.Model):
    __tablename__ = 'superadminpanel'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    superadmin_id = db.Column(db.Integer, db.ForeignKey('superadmin.id'), nullable=False)
    allUsers = db.relationship('User', backref='superadminpanel', lazy=True)
    adminLeave = db.relationship('AdminLeave', backref='superadminpanel', lazy=True)
    adminDetails = db.relationship('AdminDetail', backref='superadminpanel',uselist=False, lazy=True)
    adminDocs = db.relationship('AdminDoc', backref='superadminpanel', lazy=True)
    adminAnnouncement = db.relationship('Announcement', backref='superadminpanel', lazy=True)
    adminNotice = db.relationship('Notice', backref='superadminpanel', lazy=True)
    adminBonusPolicy = db.relationship('BonusPolicy', backref='superadminpanel', lazy=True)
    adminTimePolicy = db.relationship('ShiftTimeManagement', backref='superadminpanel', lazy=True)
    adminRemotePolicy = db.relationship('RemotePolicy', backref='superadminpanel', lazy=True)
    adminPayrollPolicy = db.relationship('PayrollPolicy', backref='superadminpanel', lazy=True)
    adminTaskManagement = db.relationship('TaskManagement', backref='superadminpanel', lazy=True)
    adminHolidays = db.relationship('AdminHoliday', backref='superadminpanel', lazy=True)
    adminDepartment = db.relationship('AdminDepartment', backref='superadminpanel', lazy=True)
    adminLocation = db.relationship('AdminLocation', backref='superadminpanel', lazy=True, uselist=False)


class AdminLocation(db.Model):
    __tablename__ = 'adminlocation'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    superpanel =  db.Column(db.Integer, db.ForeignKey('superadminpanel.id'), nullable=False)
    latitude = db.Column(db.String(255))
    longitude = db.Column(db.String(255))

class AdminDepartment(db.Model):
    __tablename__ = 'department'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(120),nullable=False)
    superpanel = db.Column(db.Integer, db.ForeignKey('superadminpanel.id'), nullable=False)


class AdminHoliday(db.Model):
    __tablename__ = 'adminholiday'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    superpanel = db.Column(db.Integer, db.ForeignKey('superadminpanel.id'), nullable=False)
    date = db.Column(db.Date, unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    country = db.Column(db.String(10), nullable=False, default='IN')
    year = db.Column(db.Integer, nullable=False)
    is_enabled = db.Column(db.Boolean, default=True)


class AdminDetail(db.Model):
    __tablename__ = 'admindetail'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    superpanel = db.Column(db.Integer, db.ForeignKey('superadminpanel.id'), nullable=False)
    legalCompanyName = db.Column(db.String(250))
    panNumber = db.Column(db.String(250))
    cinNumber = db.Column(db.String(250))
    udyamNumber = db.Column(db.String(250))
    gstNumber = db.Column(db.String(250))
    officialmail = db.Column(db.String(250))
    phoneNumber = db.Column(db.Integer)
    linkedin = db.Column(db.String(250))
    twitter = db.Column(db.String(250))
    ceo = db.Column(db.String(250))
    cto = db.Column(db.String(250))
    hrmanager = db.Column(db.String(250))
    headOffice = db.Column(db.String(120))
    state = db.Column(db.String(255))
    zipCode = db.Column(db.String(255))
    city = db.Column(db.String(255))
    country = db.Column(db.String(120))
    location = db.Column(db.String(120))


class Announcement(db.Model):
    __tablename__ = 'announcement'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    title = db.Column(db.String(255), nullable=False)
    content = db.Column(db.Text)
    images = db.Column(db.JSON)
    video = db.Column(db.String(255))
    scheduled_time = db.Column(db.DateTime, nullable=True)
    is_published = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Optional poll
    poll_question = db.Column(db.String(255), nullable=True)
    poll_option_1 = db.Column(db.String(255), nullable=True)
    poll_option_2 = db.Column(db.String(255), nullable=True)
    poll_option_3 = db.Column(db.String(255), nullable=True)
    poll_option_4 = db.Column(db.String(255), nullable=True)

    votes_option_1 = db.Column(db.Integer, default=0)
    votes_option_2 = db.Column(db.Integer, default=0)
    votes_option_3 = db.Column(db.Integer, default=0)
    votes_option_4 = db.Column(db.Integer, default=0)

    #relations
    adminPanelId = db.Column(db.Integer, db.ForeignKey('superadminpanel.id'),nullable=False)
    likes = db.relationship('Likes', backref='announcement', cascade='all, delete-orphan')
    comments = db.relationship('Comments', backref='announcement', cascade='all, delete-orphan')


class Likes(db.Model):
    __tablename__ = 'likes'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    announcement_id = db.Column(db.Integer, db.ForeignKey('announcement.id'), nullable=False)
    empId = db.Column(db.String(120))
    liked_at = db.Column(db.DateTime, default=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint('announcement_id', 'empId', name='unique_user_like'),)


class Comments(db.Model):
    __tablename__ = 'comments'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    announcement_id = db.Column(db.Integer, db.ForeignKey('announcement.id'), nullable=False)
    empId = db.Column(db.Integer)
    comments = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Notice(db.Model):
    __tablename__ = 'notice'
    id = db.Column(db.Integer, primary_key=True, autoincrement=False)
    superpanel = db.Column(db.Integer, db.ForeignKey('superadminpanel.id'), nullable=False)
    notice = db.Column(db.Text)
    createdAt = db.Column(db.DateTime, default=datetime.utcnow())


class AdminDoc(db.Model):
    __tablename__ = 'admindocuments'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    superadminPanel = db.Column(db.Integer, db.ForeignKey('superadminpanel.id'), nullable=False)
    document = db.Column(db.String(255))
    title = db.Column(db.String(255))


class AdminLeave(db.Model):
    __tablename__ = 'adminleave'
    id = db.Column(db.Integer, primary_key=True)
    superadminPanel = db.Column(db.Integer, db.ForeignKey('superadminpanel.id'), nullable=False)
    leaveName = db.Column(db.String(120), nullable=False)
    leaveType = db.Column(db.Enum('casual', 'sick', name='leave_type_enum'), default='casual', nullable=False)

    #rules for leave
    probation = db.Column(db.Boolean, default=True)
    lapse_policy = db.Column(db.Boolean, default=False)
    calculationType = db.Column(db.Enum('monthly', 'quarterly', 'annually', name='leave_calculation_type'), default='annually', nullable=False)
    day_type = db.Column(db.Enum('fullday', 'halfday', name='day_type_enum'), default='fullday', nullable=False)
    encashment = db.Column(db.Boolean, default=False)
    carryforward = db.Column(db.Boolean, default=False)
    max_leave_once = db.Column(db.Integer)
    max_leave_year = db.Column(db.Integer)
    monthly_leave_limit = db.Column(db.Integer)


class ShiftTimeManagement(db.Model):
    __tablename__ = 'shiftandtimemanagement'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    shiftName = db.Column(db.String(120), nullable=False)
    shiftType = db.Column(
        ENUM('dayshift', 'nightshift', name='work_shift_type'),
        default='dayshift', nullable=False
    )
    shiftStatus = db.Column(
        db.Boolean, default=False
    )
    shiftStart = db.Column(db.DateTime, nullable=False)
    shiftEnd = db.Column(db.DateTime, nullable=False)
    GraceTime = db.Column(db.DateTime, nullable=False)
    MaxEarly = db.Column(db.DateTime, nullable=False)
    MaxLateEntry = db.Column(db.DateTime, nullable=False)
    HalfDayThreshhold = db.Column(db.DateTime, nullable=False)
    OverTimeCountAfter = db.Column(db.DateTime, nullable=False)
    Biometric = db.Column(db.Boolean, default=False)
    RemoteCheckIn = db.Column(db.Boolean, default=False)
    workingDays = db.Column(db.JSON, nullable=True)
    saturdayCondition = db.Column(db.String(120),nullable=True)
    # AutoLogout = db.Column(db.Boolean, default=True)
    ShiftSwap = db.Column(db.Boolean, default=False)

    #relation
    superpanel = db.Column(db.Integer, db.ForeignKey('superadminpanel.id'), nullable=False)


class BonusPolicy(db.Model):
    __tablename__ = 'bonuspolicy'
    id = db.Column(db.Integer, primary_key=True)
    superPanelID = db.Column(db.Integer, db.ForeignKey('superadminpanel.id'), nullable=False)
    bonus_name = db.Column(db.String(120),nullable=False)
    bonus_method = db.Column(
        ENUM('fixed', 'percentage', name='bonus_methods_enum'),
        default='fixed',
        nullable=False
    )
    amount = db.Column(db.Integer, nullable=False)
    apply = db.Column(
        ENUM('employeementType', 'department', name='apply_method_enum'),
        default='employeementType',
        nullable=False
    )
    employeement_type = db.Column(db.String(120))
    department_type = db.Column(db.String(120))


class RemotePolicy(db.Model):
    __tablename__ = 'remotepolicy'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    remoteName = db.Column(db.String(120))
    remoteStatus = db.Column(db.Boolean, default=False)
    max_remote_day = db.Column(db.Integer)
    approval = db.Column(db.Boolean, default=False)
    allowed_department = db.Column(db.String(120))
    equipment_provided = db.Column(db.Boolean, default=False)
    superPanel = db.Column(db.Integer, db.ForeignKey('superadminpanel.id'), nullable=False)


class PayrollPolicy(db.Model):
    __tablename__ = 'payrollpolicy'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    policyname = db.Column(db.String(120))
    calculation_method = db.Column(
        ENUM('fixed' , 'attendancebased', name='calculation_method_name'),
        default = 'attendancebased'
    )
    overtimePolicy = db.Column(
        ENUM('paid', 'notapplicable', name = 'overtimePolicy_name'),
        default = 'paid'
    )
    perhour = db.Column(db.Integer)
    pfDeduction = db.Column(db.Boolean, default=False)
    salaryHoldCondition = db.Column(JSON)
    disbursement = db.Column(db.DateTime)
    employeementType = db.Column(
        ENUM('fulltime', 'parttime', name = 'employeement_type')
    )
    departmentType = db.Column(db.String(120))
    superpanel = db.Column(db.Integer, db.ForeignKey('superadminpanel.id'), nullable=False)


# ====================================
#           USER SECTION              
# ====================================


class User(db.Model):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    
    # Personal Information
    superadminId = db.Column(db.String(120), nullable=False)    # admins super id
    profileImage = db.Column(db.String(200))
    userName = db.Column(db.String(100), nullable=False)
    empId = db.Column(db.String(20), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(512), nullable=False)
    gender = db.Column(db.String(120))
    shift = db.Column(
        ENUM('dayshift', 'nightshift', name='user_shift'),
        default='dayshift'
    )
    workType = db.Column(
        ENUM('onsite', 'remote', name='work_type_name'),
        default='onsite',
    )
    
    # Contact Information
    number = db.Column(db.String(20))
    currentAddress = db.Column(db.String(200))
    permanentAddress = db.Column(db.String(200))
    birthday = db.Column(db.DateTime)
    postal = db.Column(db.String(20))
    city = db.Column(db.String(120))
    state = db.Column(db.String(120))
    country = db.Column(db.String(120))
    nationality = db.Column(db.String(100))
    
    # Government IDs
    panNumber = db.Column(db.String(20))
    adharNumber = db.Column(db.String(20))
    uanNumber = db.Column(db.String(20))
    
    # Employment Information
    department = db.Column(db.String(120))
    onBoardingStatus = db.Column(db.String(100))
    sourceOfHire = db.Column(db.String(100))
    currentSalary = db.Column(db.Integer)
    joiningDate = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Education Information
    schoolName = db.Column(db.String(200)) 
    degree = db.Column(db.String(120))
    fieldOfStudy = db.Column(db.String(120))
    dateOfCompletion = db.Column(db.Date)
    
    # Skills and Experience
    skills = db.Column(db.Text)
    occupation = db.Column(db.String(120))
    company = db.Column(db.String(120))
    experience = db.Column(db.Integer)
    duration = db.Column(db.String(50))
    userRole = db.Column(db.String(50), nullable=False)
    managerId = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    superadmin_panel_id = db.Column(db.Integer, db.ForeignKey('superadminpanel.id'), nullable=False)
    panelData = db.relationship('UserPanelData', uselist=False, backref='user', lazy=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class UserAccess(db.Model):
    __tablename__ = 'useraccess'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    section = db.Column(db.String(100), nullable=False)      # e.g., "salary", "ticket", "leave"
    permission = db.Column(db.String(100), nullable=False)   # e.g., "view", "edit", "assign", "delete"
    allowed = db.Column(db.Boolean, default=False)           # True or False
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship('User', backref='access_permissions')


class UserPanelData(db.Model):
    __tablename__ = 'userpaneldata'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    userPersonalData = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, unique=True)
    
    # Relationships
    userPunchData = db.relationship('PunchData', backref='user_panel', lazy=True)
    userLeaveData = db.relationship('UserLeave', backref='user_panel', lazy=True)
    userSalaryDetails = db.relationship('UserSalary', backref='user_panel', lazy=True)  #user will set his basic salary details
    employeeRequest = db.relationship('EmployeeRequest', backref='user_panel', lazy=True)
    userJobInfo = db.relationship('JobInfo', backref='user_panel', lazy=True)
    UserAcheivements = db.relationship('UserAcheivements', backref='user_panel', lazy=True)
    UserHolidays = db.relationship('UserHoliday', backref='user_panel', lazy=True)
    UserTicket = db.relationship('UserTicket', backref='user_panel', lazy=True)
    UserDocuments = db.relationship('UserDocument', backref='user_panel', lazy=True)
    UserSalary = db.relationship('UserSalaryDetails', backref='user_panel', lazy=True)    #admin will post the salary 
    UserMessage = db.relationship('UserChat', backref='user_panel', lazy=True)
    MyTasks = db.relationship('TaskUser', backref='user_panel', lazy=True)
    MyAssets = db.relationship('ProductAsset', backref='user_panel', lazy=True)
    UserPromotion = db.relationship('UserPromotion', backref='user_panel', lazy=True)


class ProductAsset(db.Model):
    __tablename__ = 'productasset'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    superpanel = db.Column(db.Integer, db.ForeignKey('userpaneldata.id'), nullable=False)
    productId = db.Column(db.String(100))
    productName = db.Column(db.String(200))
    category = db.Column(db.String(100))
    qty = db.Column(db.Integer, default=1)
    dateofrequest = db.Column(db.DateTime, default=datetime.utcnow)
    department = db.Column(db.String(120))
    purchaseDate = db.Column(db.Date, default=datetime.utcnow)
    warrantyTill = db.Column(db.Date, nullable=True)
    condition = db.Column(db.String(100)) 
    status = db.Column(db.String(100), nullable=False)
    location = db.Column(db.String(200))
    assignedTo = db.Column(db.String(120))
    username = db.Column(db.String(120))


class UserChat(db.Model):
    __tablename__ = 'messages'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    panelData = db.Column(db.Integer, db.ForeignKey('userpaneldata.id'), nullable=False)
    senderID = db.Column(db.String(120),nullable=False)
    recieverID = db.Column(db.String(120), nullable=False)
    message = db.Column(db.Text, nullable=True)
    image_url = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class TaskManagement(db.Model):
    __tablename__ = 'taskmanagement'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    superpanelId = db.Column(db.Integer, db.ForeignKey('superadminpanel.id'), nullable=False)
    title = db.Column(db.String(120))
    description = db.Column(db.String(255))
    assignedAt = db.Column(db.DateTime, default=datetime.utcnow)
    lastDate = db.Column(db.DateTime)
    links = db.Column(db.JSON)
    files = db.Column(db.JSON)
    status = db.Column(db.String(120))
    done = db.Column(db.String(120))
    comments = db.relationship('TaskComments',backref='taskmanagement', cascade='all, delete-orphan')
    users = db.relationship('TaskUser',backref='taskmanagement', cascade='all, delete-orphan')


class TaskComments(db.Model):
    __tablename__ = 'taskcomment'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    taskPanelId = db.Column(db.Integer, db.ForeignKey('taskmanagement.id'), nullable=False)
    taskId = db.Column(db.Integer)
    userId = db.Column(db.String(120))
    username = db.Column(db.String(120))
    comments = db.Column(db.String(255))


class TaskUser(db.Model):
    __tablename__ = 'taskuser'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    taskPanelId = db.Column(db.Integer, db.ForeignKey('taskmanagement.id'), nullable=False)
    userPanelId = db.Column(db.Integer, db.ForeignKey('userpaneldata.id'), nullable=False)
    is_completed = db.Column(db.Boolean, default=False)
    user_emp_id = db.Column(db.String(120))
    user_userName = db.Column(db.String(120))
    image = db.Column(db.String(255))


class UserSalaryDetails(db.Model):
    __tablename__ = 'usersalarydetails'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    panelDataID = db.Column(db.Integer, db.ForeignKey('userpaneldata.id'), nullable=False)
    empId = db.Column(db.String(120))
    present = db.Column(db.String(12))
    absent = db.Column(db.String(12))
    basicSalary = db.Column(db.String(12))
    deductions = db.Column(db.String(12))
    bonus = db.Column(db.Integer)
    bonus_reason = db.Column(db.Integer)
    finalPay = db.Column(db.String(12))
    mode = db.Column(db.String(12))
    status  = db.Column(db.String(12))
    payslip = db.Column(db.String(255))
    approvedLeaves = db.Column(db.String(12))
    onhold = db.Column(db.Boolean,default=False)
    onhold_reason = db.Column(db.String(255))
    createdAt = db.Column(db.DateTime, default=datetime.utcnow)


class UserLeave(db.Model):                                           #user leave
    __tablename__ = 'userleave'
    id = db.Column(db.Integer, primary_key=True)
    panelData = db.Column(db.Integer, db.ForeignKey('userpaneldata.id'),nullable=False)
    empId = db.Column(db.String(200))
    leavetype = db.Column(db.String(120))
    leavefrom = db.Column(db.DateTime)
    leaveto = db.Column(db.DateTime)
    reason = db.Column(db.String(200))

    #additional data
    name = db.Column(db.String(200))
    email = db.Column(db.String(200))
    days = db.Column(db.Integer)
    status = db.Column(db.String(100))
    unpaidDays = db.Column(db.Integer)
    createdAt = db.Column(db.DateTime, default=datetime.utcnow)


class UserTicket(db.Model):
    __tablename__ = 'userticket'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    userName = db.Column(db.String(120))
    userId = db.Column(db.String(120))
    date = db.Column(db.DateTime, default=datetime.utcnow)
    topic = db.Column(db.String(255))
    problem = db.Column(db.String(255))
    priority = db.Column(db.String(120))
    department = db.Column(db.String(120))
    document = db.Column(db.String(255))
    status = db.Column(db.String(255))
    assigned_to_empId = db.Column(db.String(120), nullable=True)
    userticketpanel = db.Column(db.Integer, db.ForeignKey('userpaneldata.id'), nullable=False)


class TicketAssignmentLog(db.Model):
    __tablename__ = 'ticketassignmentlog'
    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey('userticket.id'), nullable=False)
    assigned_by_empId = db.Column(db.String(120), nullable=False)  
    assigned_to_empId = db.Column(db.String(120), nullable=False)
    assigned_at = db.Column(db.DateTime, default=datetime.utcnow)
    ticket = db.relationship('UserTicket', backref='assignment_logs')


class EmployeeRequest(db.Model):
    __tablename__ = 'employeerequest'
    id = db.Column(db.Integer, primary_key=True)
    panelDataid = db.Column(db.Integer, db.ForeignKey('userpaneldata.id'), nullable=False)
    userName = db.Column(db.String(100), nullable=False)
    userId = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    department = db.Column(db.String(100), nullable=False)
    requestDate = db.Column(db.DateTime, default=datetime.utcnow)
    itemType = db.Column(db.String(100), nullable=False)
    quantity = db.Column(db.String(100))
    action = db.Column(db.String(50))


class JobInfo(db.Model):
    __tablename__ = 'jobinfo'
    id = db.Column(db.Integer, primary_key=True)
    panelData = db.Column(db.Integer, db.ForeignKey('userpaneldata.id'), nullable=False)
    position = db.Column(db.String(120))
    jobLevel = db.Column(db.String(120))
    department = db.Column(db.String(120))
    location = db.Column(db.String(120))
    reporting_manager = db.Column(db.String(120))
    join_date = db.Column(db.DateTime)
    total_time = db.Column(db.String(120))
    employement_type = db.Column(db.String(120))
    probation_period = db.Column(db.String(120))
    notice_period = db.Column(db.String(120))
    contract_number = db.Column(db.String(120))
    contract_type = db.Column(db.String(120))
    start_date = db.Column(db.DateTime)
    end_date = db.Column(db.DateTime)
    working_type = db.Column(db.String(120))
    shift_time = db.Column(db.DateTime)
    previous_position = db.Column(db.String(120))
    position_date = db.Column(db.DateTime)
    transfer_location = db.Column(db.String(120))
    reason_for_change = db.Column(db.String(120))


class UserDocument(db.Model):
    __tablename__ = 'userdocument'
    id = db.Column(db.Integer, primary_key=True)
    panelDataID = db.Column(db.Integer, db.ForeignKey('userpaneldata.id'), nullable=False)
    documents = db.Column(db.String(255))
    title = db.Column(db.String(120))


class UserAcheivements(db.Model):
    __tablename__ = 'useracheivement'
    id = db.Column(db.Integer, primary_key=True)
    panelDataId = db.Column(db.Integer, db.ForeignKey('userpaneldata.id'), nullable=False)
    date = db.Column(db.DateTime)
    title = db.Column(db.String(120))
    acheivement = db.Column(db.String(120))


class UserSalary(db.Model):
    __tablename__ = 'usersalary'
    id = db.Column(db.Integer, primary_key=True)
    panelData = db.Column(db.Integer, db.ForeignKey('userpaneldata.id'),nullable=False)
    payType = db.Column(db.String(200))
    ctc = db.Column(db.Integer)
    baseSalary = db.Column(db.Integer)
    currency = db.Column(db.String(200))
    paymentMode = db.Column(db.String(200))
    bankName = db.Column(db.String(200))
    accountNumber = db.Column(db.String(200))
    IFSC = db.Column(db.String(200))


class PunchData(db.Model):
    __tablename__ = 'punchdata'
    id = db.Column(db.Integer, primary_key=True)
    panelData = db.Column(db.Integer, db.ForeignKey('userpaneldata.id'),nullable=False)
    image = db.Column(db.String(512))
    empId = db.Column(db.String(120),nullable=False)
    name = db.Column(db.String(200))
    email = db.Column(db.String(200))
    login = db.Column(db.DateTime)
    logout = db.Column(db.DateTime)
    location = db.Column(db.String(200))
    totalhour = db.Column(db.TIME)
    productivehour = db.Column(db.DateTime)
    shift = db.Column(db.DateTime)
    status = db.Column(db.String(200))


class UserHoliday(db.Model):
    __tablename__ = 'userholidays'
    id = db.Column(db.Integer,primary_key=True)
    panelData = db.Column(db.Integer, db.ForeignKey('userpaneldata.id'),nullable=False)
    name = db.Column(db.String(200))
    day = db.Column(db.String(200))
    holidayfrom = db.Column(db.DateTime)
    holidayto = db.Column(db.DateTime)
    days = db.Column(db.Integer)
    shift = db.Column(db.String(200))
    type = db.Column(db.String(200))
    description = db.Column(db.String(200))


class UserPromotion(db.Model):
    __tablename__ = 'userpromotion'
    id = db.Column(db.Integer, primary_key=True, autoincrement=False)
    empId = db.Column(db.String(120), nullable=False)
    new_designation = db.Column(db.String(120), nullable=False)
    previous_department = db.Column(db.String(120),nullable=False)
    new_department = db.Column(db.String(120), nullable=False)
    description = db.Column(db.String(255))
    dateofpromotion  = db.Column(db.DateTime, default=datetime.utcnow)
    userpanel = db.Column(db.Integer, db.ForeignKey('userpaneldata.id'), nullable=False)