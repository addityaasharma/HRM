from models import db


# Create a system where multiple Students can enroll in multiple Courses.

# Models: Student, Course, and an association table like enrollments

# Relationship: Many-to-Many

class Student(db.Model):
    __tablename__ = 'student'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    studentname = db.Column(db.String(120))
    book = db.relationship('Course', backref='student', lazy=True)

class Course(db.Model):
    __tablename__ = 'course'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    coursename= db.Column(db.String(120))
    student = db.relationship('Student', backref='course', lazy=True)