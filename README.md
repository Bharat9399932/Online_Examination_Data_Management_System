# Online Examination Data Management System

A responsive website prototype based on the uploaded TA-1 / TA-2 project report. It uses Python, Flask, SQLite, HTML, and CSS.

## Features
- Student registration with email validation and duplicate-email prevention
- Login/logout with password hashing
- Student dashboard with active exams and recent attempts
- MCQ exam attempt and automatic evaluation
- Results with percentage and answer review
- Attempt history
- Admin dashboard with student/exam/attempt counts
- Admin can create exams, add/delete questions, and activate/deactivate exams
- SQLite database is created automatically on first run
- Sample exam and questions are seeded automatically

## Requirements
- Python 3.10 or newer recommended

## Run on Windows
1. Extract the ZIP.
2. Open the extracted folder in VS Code or Command Prompt.
3. Create a virtual environment (recommended):
   ```bat
   python -m venv .venv
   .venv\Scripts\activate
   ```
4. Install dependencies:
   ```bat
   pip install -r requirements.txt
   ```
5. Start the app:
   ```bat
   python app.py
   ```
6. Open `http://127.0.0.1:5000` in your browser.

## Run on macOS / Linux
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```
Then open `http://127.0.0.1:5000`.

## Default admin login
- Email: `admin@example.com`
- Password: `Admin@123`

Change the default admin password / account before using this beyond a classroom demo. The starter app is intended for local demonstration, not production deployment.

## Database
SQLite database file `exam_system.db` is generated automatically in this folder. Delete that file to reset the demo database and seeded sample data.

## Security notes
- Passwords are hashed using Werkzeug's password hashing helpers.
- Use a strong `SECRET_KEY` environment variable for any deployment.
- This is a classroom prototype. Before public deployment, add CSRF protection, rate limiting, robust session/cookie settings, audit logging, and production server configuration.
