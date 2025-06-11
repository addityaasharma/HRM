from flask import Flask
from config import db
import request

from models import *
from flask import jsonify

user_route = 

@user_route.route('/user', methods=['POST'])
def user():
    data = request.get_json()

    try:
        new_user = User(name=data['name'], email=data['email'])
        db.session.add(new_user)
        db.session.commit()
        return jsonify({"message": "User created successfully"}), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400


@user_route.route('/user-signup', methods=['POST'])
def user_signup():
    
