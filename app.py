import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "fallback_secret_key_for_dev")

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{os.path.join(BASE_DIR, 'tasklist.db')}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    creator = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(500), nullable=False)
    due_date = db.Column(db.Date, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    completed = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

with app.app_context():
    db.create_all()

@app.route("/", methods=["GET"])
def index():
    tasks = Task.query.order_by(Task.completed.asc(), Task.created_at.desc()).all()
    
    total_tasks = len(tasks)
    completed_tasks = sum(1 for t in tasks if t.completed)
    pending_tasks = total_tasks - completed_tasks
    progress_percentage = int((completed_tasks / total_tasks * 100)) if total_tasks > 0 else 0
    
    return render_template(
        "index.html", 
        tasks=tasks, 
        total_tasks=total_tasks, 
        completed_tasks=completed_tasks, 
        pending_tasks=pending_tasks,
        progress_percentage=progress_percentage
    )

@app.route("/submit", methods=["POST"])
def submit_task():
    creator = request.form.get("creator")
    description = request.form.get("description")
    due_date_str = request.form.get("due_date")
    
    due_date = None
    if due_date_str:
        due_date = datetime.strptime(due_date_str, '%Y-%m-%d').date()
    
    if creator and description:
        new_task = Task(creator=creator, description=description, due_date=due_date)
        db.session.add(new_task)
        db.session.commit()
        flash("Task submitted successfully!", "success")
    else:
        flash("Please provide both your name and a task description.", "error")
        
    return redirect(url_for("index"))

@app.route("/complete/<int:task_id>", methods=["POST"])
def complete_task(task_id):
    task = Task.query.get_or_404(task_id)
    task.completed = not task.completed
    db.session.commit()
    return redirect(url_for("index"))

@app.route("/delete/<int:task_id>", methods=["POST"])
def delete_task(task_id):
    task = Task.query.get_or_404(task_id)
    db.session.delete(task)
    db.session.commit()
    flash("Task deleted.", "success")
    return redirect(url_for("index"))

@app.route("/edit/<int:task_id>", methods=["GET", "POST"])
def edit_task(task_id):
    task = Task.query.get_or_404(task_id)
    if request.method == "POST":
        task.description = request.form.get("description")
        due_date_str = request.form.get("due_date")
        if due_date_str:
            task.due_date = datetime.strptime(due_date_str, '%Y-%m-%d').date()
        else:
            task.due_date = None
        task.notes = request.form.get("notes")
        db.session.commit()
        flash("Task updated successfully.", "success")
        return redirect(url_for("index"))
        
    return render_template("edit.html", task=task)

if __name__ == "__main__":
    app.run(debug=True, port=5001)
