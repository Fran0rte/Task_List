import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "fallback_secret_key_for_dev")

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{os.path.join(BASE_DIR, 'tasklist.db')}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    folders = db.relationship('Folder', backref='owner', lazy=True, cascade="all, delete-orphan")
    tasks = db.relationship('Task', backref='owner', lazy=True, cascade="all, delete-orphan")

class Folder(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    tasks = db.relationship('Task', backref='folder', lazy=True, cascade="all, delete-orphan")

class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    creator = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(500), nullable=False)
    due_date = db.Column(db.Date, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    completed = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    folder_id = db.Column(db.Integer, db.ForeignKey('folder.id'), nullable=True)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

with app.app_context():
    # We rely on deleting the tasklist.db manually from bash for schema updates
    db.create_all()

@app.route("/", methods=["GET"])
def index():
    if not current_user.is_authenticated:
        return render_template("welcome.html")
        
    folders = Folder.query.filter_by(user_id=current_user.id).all()
    tasks = Task.query.filter_by(user_id=current_user.id).order_by(Task.completed.asc(), Task.created_at.desc()).all()
    
    total_tasks = len(tasks)
    completed_tasks = sum(1 for t in tasks if t.completed)
    pending_tasks = total_tasks - completed_tasks
    progress_percentage = int((completed_tasks / total_tasks * 100)) if total_tasks > 0 else 0
    
    return render_template(
        "index.html", 
        tasks=tasks, 
        folders=folders,
        total_tasks=total_tasks, 
        completed_tasks=completed_tasks, 
        pending_tasks=pending_tasks,
        progress_percentage=progress_percentage
    )

@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        if User.query.filter_by(username=username).first():
            flash("Username already exists", "error")
            return redirect(url_for("register"))
        hashed_pw = generate_password_hash(password)
        new_user = User(username=username, password_hash=hashed_pw)
        db.session.add(new_user)
        db.session.commit()
        
        default_folder = Folder(name="General", user_id=new_user.id)
        db.session.add(default_folder)
        db.session.commit()
        
        login_user(new_user)
        return redirect(url_for("index"))
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for("index"))
        else:
            flash("Invalid username or password", "error")
    return render_template("login.html")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("index"))

@app.route("/create_folder", methods=["POST"])
@login_required
def create_folder():
    name = request.form.get("name")
    if name:
        folder = Folder(name=name, user_id=current_user.id)
        db.session.add(folder)
        db.session.commit()
        flash("Folder created!", "success")
    return redirect(url_for("index"))

@app.route("/submit", methods=["POST"])
@login_required
def submit_task():
    creator = current_user.username
    description = request.form.get("description")
    due_date_str = request.form.get("due_date")
    folder_id = request.form.get("folder_id")
    if not folder_id:
        folder_id = None
    
    due_date = None
    if due_date_str:
        due_date = datetime.strptime(due_date_str, '%Y-%m-%d').date()
    
    if description:
        new_task = Task(creator=creator, description=description, due_date=due_date, folder_id=folder_id, user_id=current_user.id)
        db.session.add(new_task)
        db.session.commit()
        flash("Task submitted successfully!", "success")
    else:
        flash("Please provide a task description.", "error")
        
    return redirect(url_for("index"))

@app.route("/complete/<int:task_id>", methods=["POST"])
@login_required
def complete_task(task_id):
    task = Task.query.filter_by(id=task_id, user_id=current_user.id).first_or_404()
    task.completed = not task.completed
    db.session.commit()
    return redirect(url_for("index"))

@app.route("/delete/<int:task_id>", methods=["POST"])
@login_required
def delete_task(task_id):
    task = Task.query.filter_by(id=task_id, user_id=current_user.id).first_or_404()
    db.session.delete(task)
    db.session.commit()
    flash("Task deleted.", "success")
    return redirect(url_for("index"))

@app.route("/edit/<int:task_id>", methods=["GET", "POST"])
@login_required
def edit_task(task_id):
    task = Task.query.filter_by(id=task_id, user_id=current_user.id).first_or_404()
    if request.method == "POST":
        task.description = request.form.get("description")
        due_date_str = request.form.get("due_date")
        if due_date_str:
            task.due_date = datetime.strptime(due_date_str, '%Y-%m-%d').date()
        else:
            task.due_date = None
        task.notes = request.form.get("notes")
        folder_id = request.form.get("folder_id")
        task.folder_id = folder_id if folder_id else None
        db.session.commit()
        flash("Task updated successfully.", "success")
        return redirect(url_for("index"))
        
    folders = Folder.query.filter_by(user_id=current_user.id).all()
    return render_template("edit.html", task=task, folders=folders)

if __name__ == "__main__":
    app.run(debug=True, port=5001)
