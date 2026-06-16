from flask import Flask, render_template, request, redirect, url_for, session
import qrcode
import os
import cv2
import sqlite3
from datetime import datetime
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "your_secret_key_change_this"

GENERATED_FOLDER = "static/generated"
os.makedirs(GENERATED_FOLDER, exist_ok=True)

DATABASE = "users.db"


def get_db():
    return sqlite3.connect(DATABASE)


def init_db():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            action_type TEXT NOT NULL,
            input_value TEXT,
            output_value TEXT,
            qr_image TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """)

    conn.commit()
    conn.close()


init_db()


def login_required():
    return "user_id" in session


@app.route("/")
def home():
    if not login_required():
        return redirect(url_for("login"))

    return render_template("index.html", mode=None, username=session.get("username"))


@app.route("/signup", methods=["GET", "POST"])
def signup():
    error = None
    success = None

    if request.method == "POST":
        username = request.form.get("username")
        email = request.form.get("email")
        password = request.form.get("password")

        if not username or not email or not password:
            error = "All fields are required."
        else:
            hashed_password = generate_password_hash(password)

            try:
                conn = get_db()
                cursor = conn.cursor()

                cursor.execute(
                    "INSERT INTO users (username, email, password) VALUES (?, ?, ?)",
                    (username, email, hashed_password)
                )

                conn.commit()
                conn.close()

                success = "Account created successfully. Please login."

            except sqlite3.IntegrityError:
                error = "Username or email already exists."

    return render_template("signup.html", error=error, success=success)


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None

    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
        user = cursor.fetchone()

        conn.close()

        if user and check_password_hash(user[3], password):
            session["user_id"] = user[0]
            session["username"] = user[1]
            return redirect(url_for("home"))
        else:
            error = "Invalid email or password."

    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/link-to-qr", methods=["GET", "POST"])
def link_to_qr():
    if not login_required():
        return redirect(url_for("login"))

    qr_image = None
    error = None

    if request.method == "POST":
        link = request.form.get("link")

        if not link:
            error = "Please enter a valid link."
        else:
            qr = qrcode.QRCode(version=1, box_size=10, border=4)
            qr.add_data(link)
            qr.make(fit=True)

            img = qr.make_image(fill_color="black", back_color="white")

            filename = f"qr_user_{session['user_id']}_{datetime.now().strftime('%Y%m%d%H%M%S')}.png"
            filepath = os.path.join(GENERATED_FOLDER, filename)
            img.save(filepath)

            qr_image = filepath

            conn = get_db()
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO history
                (user_id, action_type, input_value, output_value, qr_image, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                session["user_id"],
                "Link to QR",
                link,
                "QR Code Generated",
                qr_image,
                datetime.now().strftime("%d %b %Y, %I:%M %p")
            ))

            conn.commit()
            conn.close()

    return render_template(
        "index.html",
        mode="link_to_qr",
        qr_image=qr_image,
        error=error,
        username=session.get("username")
    )


@app.route("/qr-to-link", methods=["GET", "POST"])
def qr_to_link():
    if not login_required():
        return redirect(url_for("login"))

    decoded_text = None
    error = None

    if request.method == "POST":
        file = request.files.get("qr_image")

        if not file:
            error = "Please upload a QR image."
        else:
            filename = secure_filename(file.filename)

            filepath = os.path.join(
                GENERATED_FOLDER,
                f"user_{session['user_id']}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{filename}"
            )

            file.save(filepath)

            image = cv2.imread(filepath)

            if image is None:
                error = "Invalid image file."
            else:
                detector = cv2.QRCodeDetector()
                data, points, _ = detector.detectAndDecode(image)

                if data:
                    decoded_text = data

                    conn = get_db()
                    cursor = conn.cursor()

                    cursor.execute("""
                        INSERT INTO history
                        (user_id, action_type, input_value, output_value, qr_image, created_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        session["user_id"],
                        "QR to Link",
                        filepath,
                        decoded_text,
                        None,
                        datetime.now().strftime("%d %b %Y, %I:%M %p")
                    ))

                    conn.commit()
                    conn.close()

                else:
                    error = "Could not read QR code. Please upload a clear QR image."

    return render_template(
        "index.html",
        mode="qr_to_link",
        decoded_text=decoded_text,
        error=error,
        username=session.get("username")
    )


@app.route("/dashboard")
def dashboard():
    if not login_required():
        return redirect(url_for("login"))

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT action_type, input_value, output_value, qr_image, created_at
        FROM history
        WHERE user_id = ?
        ORDER BY id DESC
    """, (session["user_id"],))

    history = cursor.fetchall()

    cursor.execute("""
        SELECT COUNT(*)
        FROM history
        WHERE user_id = ? AND action_type = 'Link to QR'
    """, (session["user_id"],))
    qr_count = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(*)
        FROM history
        WHERE user_id = ? AND action_type = 'QR to Link'
    """, (session["user_id"],))
    decoded_count = cursor.fetchone()[0]

    total_count = qr_count + decoded_count

    qr_percentage = round((qr_count / total_count) * 100, 1) if total_count > 0 else 0
    decoded_percentage = round((decoded_count / total_count) * 100, 1) if total_count > 0 else 0

    conn.close()

    return render_template(
        "dashboard.html",
        history=history,
        username=session.get("username"),
        qr_count=qr_count,
        decoded_count=decoded_count,
        total_count=total_count,
        qr_percentage=qr_percentage,
        decoded_percentage=decoded_percentage
    )


if __name__ == "__main__":
    app.run(debug=True)