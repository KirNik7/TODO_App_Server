from flask import Flask, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from flask_cors import CORS
from flask_migrate import Migrate
from sqlalchemy import case
from flask_bcrypt import Bcrypt
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from dotenv import load_dotenv
import os


load_dotenv()
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URI')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY')

db = SQLAlchemy(app)
migrate = Migrate(app, db)
bcrypt = Bcrypt(app)
jwt = JWTManager(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)


class Board(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    tasks = db.relationship('Task', backref='board', cascade='all, delete-orphan')


class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    board_id = db.Column(db.Integer, db.ForeignKey('board.id', ondelete='CASCADE'), nullable=False)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    due_date = db.Column(db.DateTime, nullable=True)
    priority = db.Column(db.String(50), nullable=True)
    completed = db.Column(db.Boolean, default=False)
    status = db.Column(db.String(50), nullable=False, default="в работе")

@app.route('/register', methods=['POST'])
def register():
    data = request.json
    email = data.get('email')
    password = data.get('password')
    if User.query.filter_by(email=email).first():
        return jsonify({"message": "User already exists"}), 400
    password = bcrypt.generate_password_hash(password).decode('utf-8')
    user = User(email=email, password=password)
    db.session.add(user)
    db.session.commit()
    return jsonify({"message": "User registered successfully"}), 201


@app.route('/login', methods=['POST'])
def login():
    data = request.json
    email = data.get('email')
    password = data.get('password')
    user = User.query.filter_by(email=email).first()
    if user and bcrypt.check_password_hash(user.password, password):
        access_token = create_access_token(identity=str(user.id))
        return jsonify({"access_token": access_token}), 200
    return jsonify({"message": "Invalid email or password"}), 401


@app.route('/user-info', methods=['GET'])
@jwt_required()
def user_info():
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    if not user:
        return jsonify({"message": "User not found"}), 404
    return jsonify({"email": user.email}), 200


@app.route('/boards', methods=['GET'])
@jwt_required()
def get_boards():
    user_id = get_jwt_identity()
    boards = Board.query.filter_by(user_id=user_id).all()
    return jsonify([{"id": board.id, "name": board.name} for board in boards])


@app.route('/boards', methods=['POST'])
@jwt_required()
def create_board():
    user_id = get_jwt_identity()
    data = request.json
    board = Board(name=data['name'], user_id=user_id)
    db.session.add(board)
    db.session.commit()
    return jsonify({"id": board.id, "name": board.name}), 201


@app.route('/boards/<int:board_id>', methods=['DELETE'])
@jwt_required()
def delete_board(board_id):
    user_id = get_jwt_identity()
    board = Board.query.filter_by(id=board_id, user_id=user_id).first()
    if not board:
        return jsonify({"message": "Board not found or access denied"}), 404
    db.session.delete(board)
    db.session.commit()
    return jsonify({"message": "Board deleted"}), 200


@app.route('/tasks', methods=['GET'])
@jwt_required()
def get_tasks():
    user_id = get_jwt_identity()
    board_id = request.args.get('board_id')
    sort_by = request.args.get('sort_by', 'priority')
    filter_status = request.args.get('status')

    query = Task.query.join(Board).filter(Board.user_id == user_id)
    if board_id:
        query = query.filter(Task.board_id == board_id)
    if filter_status:
        query = query.filter(Task.status == filter_status)
    if sort_by == 'priority':
        priority_order = case(
            (Task.priority == 'High', 1),
            (Task.priority == 'Medium', 2),
            (Task.priority == 'Low', 3),
            else_=4
        )
        query = query.order_by(priority_order, Task.due_date.asc())
    elif sort_by == 'due_date':
        query = query.order_by(Task.due_date.asc(), Task.priority.desc())

    tasks = query.all()
    return jsonify([{
        "id": task.id,
        "board_id": task.board_id,
        "title": task.title,
        "description": task.description,
        "priority": task.priority,
        "due_date": task.due_date.strftime('%Y-%m-%d %H:%M') if task.due_date else None,
        "completed": task.completed,
        "status": task.status
    } for task in tasks])


@app.route('/tasks', methods=['POST'])
@jwt_required()
def create_task():
    user_id = get_jwt_identity()
    data = request.json
    board = Board.query.filter_by(id=data['board_id'], user_id=user_id).first()
    if not board:
        return jsonify({"message": "Board not found or access denied"}), 404

    task = Task(
        board_id=board.id,
        title=data['title'],
        description=data.get('description'),
        due_date=datetime.strptime(data['due_date'], '%Y-%m-%dT%H:%M') if data.get('due_date') else None,
        priority=data.get('priority'),
        completed=False,
        status="в работе"
    )
    db.session.add(task)
    db.session.commit()

    return jsonify({
        "id": task.id,
        "board_id": task.board_id,
        "title": task.title,
        "description": task.description,
        "priority": task.priority,
        "due_date": task.due_date.strftime('%Y-%m-%d %H:%M:%S') if task.due_date else None,
        "completed": task.completed
    }), 201


@app.route('/tasks/<int:task_id>', methods=['DELETE'])
@jwt_required()
def delete_task(task_id):
    user_id = get_jwt_identity()
    task = Task.query.join(Board).filter(Task.id == task_id, Board.user_id == user_id).first()
    if not task:
        return jsonify({"message": "Task not found or access denied"}), 404
    db.session.delete(task)
    db.session.commit()
    return jsonify({"message": "Task deleted"}), 200


@app.route('/tasks/<int:task_id>', methods=['PUT'])
@jwt_required()
def update_task_completion(task_id):
    user_id = get_jwt_identity()
    task = Task.query.join(Board).filter(Task.id == task_id, Board.user_id == user_id).first()
    if not task:
        return jsonify({"message": "Task not found or access denied"}), 404
    data = request.json
    task.completed = data.get('completed', task.completed)
    db.session.commit()
    return jsonify({"id": task.id, "completed": task.completed})


@app.route('/tasks/<int:task_id>/status', methods=['PUT'])
@jwt_required()
def update_task_status(task_id):
    user_id = get_jwt_identity()
    task = Task.query.join(Board).filter(Task.id == task_id, Board.user_id == user_id).first()
    if not task:
        return jsonify({"message": "Task not found or access denied"}), 404
    data = request.json
    task.status = data.get('status', task.status)
    db.session.commit()
    return jsonify({"id": task.id, "status": task.status})


if __name__ == '__main__':
    app.run(debug=True)