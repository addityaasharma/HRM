from datetime import datetime, time
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class Master(db.Model):
    __tablename__ = 'master'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(100), nullable=False)
    company_email = db.Column(db.String(120), nullable=False)
    # admins = db.relationship('SuperAdmin', backref='master', lazy=True)

class SuperAdmin(db.Model):
    __tablename__ = 'superadmin'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    superId = db.Column(db.String(120), nullable=False)
    companyName = db.Column(db.String(100), nullable=False)
    companyEmail = db.Column(db.String(120), nullable=False)
    company_password = db.Column(db.String(250), nullable=False)
    is_super_admin = db.Column(db.Boolean, default=False)
    # master_id = db.Column(db.Integer, db.ForeignKey('master.id'), nullable=True)
    superadminPanel = db.relationship('SuperAdminPanel', backref='superadmin', uselist=False, lazy=True)

class SuperAdminPanel(db.Model):
    __tablename__ = 'superadminpanel'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    superadmin_id = db.Column(db.Integer, db.ForeignKey('superadmin.id'), nullable=False)
    allUsers = db.relationship('User', backref='superadminpanel', lazy=True)

class AdminLeave(db.Model):
    __tablename__= 'adminleave'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    superadminPanel = db.Column(db.Integer, db.ForeignKey('superadminpanel.id'), nullable=False)
    leaveType = db.Column(db.String(120))
    Quota = db.Column(db.Integer)
    LeaveStatus = db.Column(db.String(120))
    carryForward = db.Column(db.Boolean, default=True)
    active = db.Column(db.Boolean, default=True)

class User(db.Model):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    
    # Personal Information
    superadminId = db.Column(db.String(120), nullable=False)
    profileImage = db.Column(db.String(200))
    userName = db.Column(db.String(100), nullable=False)
    empId = db.Column(db.String(20), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(512), nullable=False)
    gender = db.Column(db.String(120))
    
    # Contact Information
    number = db.Column(db.String(20))
    currentAddress = db.Column(db.String(200))
    permanentAddress = db.Column(db.String(200))
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

class UserPanelData(db.Model):
    __tablename__ = 'userpaneldata'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    userPersonalData = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, unique=True)
    
    # Relationships (assuming these models exist)
    userPunchData = db.relationship('PunchData', backref='user_panel', lazy=True)
    userLeaveData = db.relationship('UserLeave', backref='user_panel', lazy=True)
    userSalaryDetails = db.relationship('UserSalary', backref='user_panel', lazy=True)
    employeeRequest = db.relationship('EmployeeRequest', backref='user_panel', lazy=True)
    userJobInfo = db.relationship('JobInfo', backref='user_panel', lazy=True)
    UserAcheivements = db.relationship('UserAcheivements', backref='user_panel', lazy=True)
    UserHolidays = db.relationship('UserHoliday', backref='user_panel', lazy=True)
    UserTicket = db.relationship('UserTicket', backref='user_panel', lazy=True)
    UserDocuments = db.relationship('UserDocument', backref='user_panel', lazy=True)
    UserSalary = db.relationship('UserSalaryDetails', backref='user_panel', lazy=True)

class UserSalaryDetails(db.Model):
    __tablename__ = 'usersalarydetails'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    panelDataID = db.Column(db.Integer, db.ForeignKey('userpaneldata.id'), nullable=False)
    empId = db.Column(db.String(120))
    present = db.Column(db.String(12))
    absent = db.Column(db.String(12))
    basicSalary = db.Column(db.String(12))
    deductions = db.Column(db.String(12))
    finalPay = db.Column(db.String(12))
    mode = db.Column(db.String(12))
    status  = db.Column(db.String(12))
    payslip = db.Column(db.String(12))
    approvedLeaves = db.Column(db.String(12))

class UserLeave(db.Model):
    __tablename__ = 'userleave'
    id = db.Column(db.Integer, primary_key=True)
    panelData = db.Column(db.Integer, db.ForeignKey('userpaneldata.id'),nullable=False)
    name = db.Column(db.String(200))
    email = db.Column(db.String(200))
    empId = db.Column(db.String(200))
    leavetype = db.Column(db.String(120))
    leavefrom = db.Column(db.DateTime)
    leaveto = db.Column(db.DateTime)
    day = db.Column(db.String(200))
    month = db.Column(db.Integer)
    reason = db.Column(db.String(200))
    attachment = db.Column(db.String(200))
    status = db.Column(db.String(100))

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
    userticketpanel = db.Column(db.Integer, db.ForeignKey('userpaneldata.id'), nullable=False)

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

class UserLeaveQuota(db.Model):
    __tablename__ = 'userleavequota'
    id = db.Column(db.Integer, primary_key=True)
    leaveType = db.Column(db.String(50))
    definedYearlyLeave = db.Column(db.Integer)
    definedMonthlyLeave = db.Column(db.Integer)  #2
    monthOfLeave = db.Column(db.Integer) #06
    user_leave_taken = db.Column(db.Integer) #00
    remaining_leave = db.Column(db.Integer) #02