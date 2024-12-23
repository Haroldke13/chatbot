from flask_sqlalchemy import SQLAlchemy
import datetime
from flask_migrate import Migrate


db = SQLAlchemy()



class User(db.Model):
    __tablename__ = 'user'  # Ensure this matches the table name in the database
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), nullable=False, unique=True)
    email = db.Column(db.String(150), nullable=False, unique=True)
    password = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(50), nullable=False)

class ChatHistory(db.Model):
    __tablename__ = 'chathistory'  # Ensure this matches the table name in the database
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    message = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.datetime.utcnow)
