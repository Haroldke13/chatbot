from flask import Flask, render_template, redirect, url_for, request, flash
from flask_bcrypt import Bcrypt
from flask_login import LoginManager, UserMixin,login_user, logout_user, login_required, current_user
from flask_socketio import SocketIO, emit
from user import db, User
from db import ChatHistory
from flask_sqlalchemy import SQLAlchemy
import datetime
from flask_migrate import Migrate


# Initialize app and extensions
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:password@localhost/chatbot_db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy()
migrate = Migrate(app, db)
db.init_app(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message_category = 'info'
socketio = SocketIO(app)






class User(db.Model, UserMixin):  # Inherit from UserMixin
    __tablename__ = 'user'  # Ensure this matches the table name in the database
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), nullable=False, unique=True)
    email = db.Column(db.String(150), nullable=False, unique=True)
    password = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(50), nullable=False)
    
    def __repr__(self):
        return f"<User {self.username}>"

    @property
    def is_active(self):
        # Custom logic to determine if the user is active
        return True  # or some condition based on your requirements

    def get_id(self):
        return str(self.id)  # Return the user ID as a string




class ChatHistory(db.Model):
    __tablename__ = 'chathistory'  # Ensure this matches the table name in the database
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    message = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.datetime.utcnow)



# Load user
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Role-based access control decorator
def role_required(role):
    def decorator(func):
        def wrapper(*args, **kwargs):
            if current_user.role != role:
                flash('Access denied!', 'danger')
                return redirect(url_for('home'))
            return func(*args, **kwargs)
        wrapper.__name__ = func.__name__
        return wrapper
    return decorator

# Routes
@app.route('/')
def home():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = bcrypt.generate_password_hash(request.form['password']).decode('utf-8')
        role = 'User'  # Default role
        new_user = User(username=username, email=email, password=password, role=role)
        db.session.add(new_user)
        db.session.commit()
        flash('Account created successfully!', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(email=email).first()
        if user and bcrypt.check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('chat'))
        flash('Invalid credentials!', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out successfully!', 'info')
    return redirect(url_for('home'))

@app.route('/chat')
@login_required
def chat():
    return render_template('chat.html')

@app.route('/admin')
@login_required
@role_required('Admin')
def admin():
    users = User.query.all()
    chats = ChatHistory.query.order_by(ChatHistory.timestamp.desc()).all()
    return render_template('admin.html', users=users, chats=chats)

# Socket.IO events
@socketio.on('send_message')
def handle_send_message(data):
    message = data['message']
    user_id = current_user.id
    new_chat = ChatHistory(user_id=user_id, message=message)
    db.session.add(new_chat)
    db.session.commit()
    emit('receive_message', {'user': current_user.username, 'message': message}, broadcast=True)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # Create tables at startup
    socketio.run(app, debug=True)
