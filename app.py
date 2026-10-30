import os
import re
import sqlite3
import secrets
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, abort
from werkzeug.security import generate_password_hash, check_password_hash

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(APP_DIR, "exam_system.db")
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", secrets.token_hex(32))

def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    with db() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'student',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS exams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT DEFAULT '',
            duration_minutes INTEGER NOT NULL DEFAULT 15,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exam_id INTEGER NOT NULL,
            question_text TEXT NOT NULL,
            option_a TEXT NOT NULL,
            option_b TEXT NOT NULL,
            option_c TEXT NOT NULL,
            option_d TEXT NOT NULL,
            correct_option TEXT NOT NULL CHECK(correct_option IN ('A','B','C','D')),
            FOREIGN KEY(exam_id) REFERENCES exams(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            exam_id INTEGER NOT NULL,
            score INTEGER NOT NULL DEFAULT 0,
            total INTEGER NOT NULL DEFAULT 0,
            started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            submitted_at TEXT,
            FOREIGN KEY(user_id) REFERENCES users(id),
            FOREIGN KEY(exam_id) REFERENCES exams(id)
        );
        CREATE TABLE IF NOT EXISTS answers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            attempt_id INTEGER NOT NULL,
            question_id INTEGER NOT NULL,
            selected_option TEXT,
            is_correct INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY(attempt_id) REFERENCES attempts(id) ON DELETE CASCADE,
            FOREIGN KEY(question_id) REFERENCES questions(id)
        );
        """)
        # Create a default admin only when the database has no users.
        count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        if count == 0:
            conn.execute(
                "INSERT INTO users(name,email,password_hash,role) VALUES(?,?,?,?)",
                ("System Admin", "admin@example.com", generate_password_hash("Admin@123"), "admin")
            )
        exam_count = conn.execute("SELECT COUNT(*) FROM exams").fetchone()[0]
        if exam_count == 0:
            cur = conn.execute(
                "INSERT INTO exams(title,description,duration_minutes) VALUES(?,?,?)",
                ("Computer Fundamentals", "Sample MCQ exam to demonstrate the examination workflow.", 10)
            )
            exam_id = cur.lastrowid
            questions = [
                (exam_id, "Which language is commonly used with Flask?", "Python", "Java", "C++", "PHP", "A"),
                (exam_id, "Which database is included with this starter project?", "MongoDB", "SQLite", "Oracle", "Redis", "B"),
                (exam_id, "What does HTML primarily define?", "Page structure", "Database schema", "Network routing", "Operating system", "A"),
                (exam_id, "Which is a secure password storage approach?", "Plain text", "Base64 only", "Password hashing", "Public URL", "C"),
                (exam_id, "Which SQL clause filters rows?", "ORDER BY", "WHERE", "GROUP BY", "CREATE", "B"),
            ]
            conn.executemany("""INSERT INTO questions
                (exam_id,question_text,option_a,option_b,option_c,option_d,correct_option)
                VALUES(?,?,?,?,?,?,?)""", questions)

def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("user_id"):
            flash("Please log in to continue.", "warning")
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapper

def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("login"))
        if session.get("role") != "admin":
            abort(403)
        return fn(*args, **kwargs)
    return wrapper

@app.context_processor
def inject_user():
    return {"current_user": session.get("name"), "current_role": session.get("role")}

@app.route("/")
def index():
    if session.get("user_id"):
        return redirect(url_for("dashboard"))
    return render_template("index.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if not name or not email or not password:
            flash("All fields are required.", "danger")
        elif not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
            flash("Please enter a valid email address.", "danger")
        elif len(password) < 8:
            flash("Password must be at least 8 characters long.", "danger")
        else:
            try:
                with db() as conn:
                    conn.execute(
                        "INSERT INTO users(name,email,password_hash,role) VALUES(?,?,?,?)",
                        (name, email, generate_password_hash(password), "student")
                    )
                flash("Account created. You can now log in.", "success")
                return redirect(url_for("login"))
            except sqlite3.IntegrityError:
                flash("This email is already registered.", "danger")
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        with db() as conn:
            user = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            session["name"] = user["name"]
            session["email"] = user["email"]
            session["role"] = user["role"]
            flash(f"Welcome back, {user['name']}!", "success")
            return redirect(url_for("dashboard"))
        flash("Incorrect email or password.", "danger")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("index"))

@app.route("/dashboard")
@login_required
def dashboard():
    with db() as conn:
        exams = conn.execute("""
            SELECT e.*, COUNT(q.id) AS question_count
            FROM exams e LEFT JOIN questions q ON q.exam_id=e.id
            WHERE e.is_active=1 GROUP BY e.id ORDER BY e.id DESC
        """).fetchall()
        attempts = conn.execute("""
            SELECT a.*, e.title FROM attempts a JOIN exams e ON e.id=a.exam_id
            WHERE a.user_id=? ORDER BY a.id DESC LIMIT 5
        """, (session["user_id"],)).fetchall()
        stats = conn.execute("""
            SELECT COUNT(*) AS attempts, COALESCE(MAX(CASE WHEN total>0 THEN ROUND(score*100.0/total) END),0) AS best
            FROM attempts WHERE user_id=? AND submitted_at IS NOT NULL
        """, (session["user_id"],)).fetchone()
    return render_template("dashboard.html", exams=exams, attempts=attempts, stats=stats)

@app.route("/exam/<int:exam_id>", methods=["GET", "POST"])
@login_required
def take_exam(exam_id):
    with db() as conn:
        exam = conn.execute("SELECT * FROM exams WHERE id=? AND is_active=1", (exam_id,)).fetchone()
        if not exam:
            abort(404)
        questions = conn.execute("SELECT * FROM questions WHERE exam_id=? ORDER BY id", (exam_id,)).fetchall()
        if request.method == "POST":
            if not questions:
                flash("This exam has no questions yet.", "warning")
                return redirect(url_for("dashboard"))
            cur = conn.execute(
                "INSERT INTO attempts(user_id,exam_id,score,total,submitted_at) VALUES(?,?,?,?,?)",
                (session["user_id"], exam_id, 0, len(questions), None)
            )
            attempt_id = cur.lastrowid
            score = 0
            for q in questions:
                selected = request.form.get(f"q_{q['id']}", "")
                correct = int(selected == q["correct_option"])
                score += correct
                conn.execute(
                    "INSERT INTO answers(attempt_id,question_id,selected_option,is_correct) VALUES(?,?,?,?)",
                    (attempt_id, q["id"], selected or None, correct)
                )
            conn.execute("UPDATE attempts SET score=?, submitted_at=? WHERE id=?",
                         (score, datetime.utcnow().isoformat(timespec="seconds"), attempt_id))
            return redirect(url_for("result", attempt_id=attempt_id))
    return render_template("exam.html", exam=exam, questions=questions)

@app.route("/result/<int:attempt_id>")
@login_required
def result(attempt_id):
    with db() as conn:
        attempt = conn.execute("""
            SELECT a.*, e.title, u.name FROM attempts a
            JOIN exams e ON e.id=a.exam_id JOIN users u ON u.id=a.user_id
            WHERE a.id=? AND a.user_id=?
        """, (attempt_id, session["user_id"])).fetchone()
        if not attempt:
            abort(404)
        answers = conn.execute("""
            SELECT q.question_text,q.option_a,q.option_b,q.option_c,q.option_d,
                   q.correct_option,ans.selected_option,ans.is_correct
            FROM answers ans JOIN questions q ON q.id=ans.question_id
            WHERE ans.attempt_id=? ORDER BY q.id
        """, (attempt_id,)).fetchall()
    percent = round(attempt["score"] * 100 / attempt["total"]) if attempt["total"] else 0
    return render_template("result.html", attempt=attempt, answers=answers, percent=percent)

@app.route("/history")
@login_required
def history():
    with db() as conn:
        attempts = conn.execute("""
            SELECT a.*, e.title FROM attempts a JOIN exams e ON e.id=a.exam_id
            WHERE a.user_id=? AND a.submitted_at IS NOT NULL ORDER BY a.id DESC
        """, (session["user_id"],)).fetchall()
    return render_template("history.html", attempts=attempts)

@app.route("/admin")
@admin_required
def admin():
    with db() as conn:
        exams = conn.execute("""
            SELECT e.*, COUNT(q.id) AS question_count FROM exams e
            LEFT JOIN questions q ON q.exam_id=e.id GROUP BY e.id ORDER BY e.id DESC
        """).fetchall()
        users = conn.execute("SELECT id,name,email,role,created_at FROM users ORDER BY id DESC").fetchall()
        totals = {
            "users": conn.execute("SELECT COUNT(*) FROM users WHERE role='student'").fetchone()[0],
            "exams": conn.execute("SELECT COUNT(*) FROM exams").fetchone()[0],
            "attempts": conn.execute("SELECT COUNT(*) FROM attempts WHERE submitted_at IS NOT NULL").fetchone()[0],
        }
    return render_template("admin.html", exams=exams, users=users, totals=totals)

@app.route("/admin/exam/new", methods=["GET", "POST"])
@admin_required
def new_exam():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        try:
            duration = max(1, min(240, int(request.form.get("duration", "15"))))
        except ValueError:
            duration = 15
        if not title:
            flash("Exam title is required.", "danger")
        else:
            with db() as conn:
                conn.execute("INSERT INTO exams(title,description,duration_minutes) VALUES(?,?,?)",
                             (title, description, duration))
            flash("Exam created. Add questions to make it available.", "success")
            return redirect(url_for("admin"))
    return render_template("exam_form.html")

@app.route("/admin/exam/<int:exam_id>/toggle", methods=["POST"])
@admin_required
def toggle_exam(exam_id):
    with db() as conn:
        conn.execute("UPDATE exams SET is_active=CASE is_active WHEN 1 THEN 0 ELSE 1 END WHERE id=?", (exam_id,))
    flash("Exam status updated.", "success")
    return redirect(url_for("admin"))

@app.route("/admin/exam/<int:exam_id>/questions", methods=["GET", "POST"])
@admin_required
def manage_questions(exam_id):
    with db() as conn:
        exam = conn.execute("SELECT * FROM exams WHERE id=?", (exam_id,)).fetchone()
        if not exam:
            abort(404)
        if request.method == "POST":
            question = request.form.get("question", "").strip()
            options = [request.form.get(f"option_{letter.lower()}", "").strip() for letter in "ABCD"]
            correct = request.form.get("correct", "A")
            if not question or any(not option for option in options) or correct not in "ABCD":
                flash("Fill in the question, all four options, and correct answer.", "danger")
            else:
                conn.execute("""INSERT INTO questions
                    (exam_id,question_text,option_a,option_b,option_c,option_d,correct_option)
                    VALUES(?,?,?,?,?,?,?)""", (exam_id, question, *options, correct))
                flash("Question added.", "success")
                return redirect(url_for("manage_questions", exam_id=exam_id))
        questions = conn.execute("SELECT * FROM questions WHERE exam_id=? ORDER BY id", (exam_id,)).fetchall()
    return render_template("questions.html", exam=exam, questions=questions)

@app.route("/admin/question/<int:question_id>/delete", methods=["POST"])
@admin_required
def delete_question(question_id):
    with db() as conn:
        question = conn.execute("SELECT exam_id FROM questions WHERE id=?", (question_id,)).fetchone()
        if not question:
            abort(404)
        exam_id = question["exam_id"]
        conn.execute("DELETE FROM questions WHERE id=?", (question_id,))
    flash("Question deleted.", "info")
    return redirect(url_for("manage_questions", exam_id=exam_id))

@app.errorhandler(403)
def forbidden(_):
    return render_template("error.html", code=403, message="You do not have permission to view this page."), 403

@app.errorhandler(404)
def not_found(_):
    return render_template("error.html", code=404, message="The page or record could not be found."), 404

init_db()

if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)
