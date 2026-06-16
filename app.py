from flask import Flask, render_template, request, redirect, url_for, session
import qrcode
import os
import cv2
import sqlite3
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "your_secret_key_change_this"

GENERATED_FOLDER = "static/generated"
os.makedirs(GENERATED_FOLDER, exist_ok=True)

DATABASE = "users.db"


def init_db():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
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
                conn = sqlite3.connect(DATABASE)
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

        conn = sqlite3.connect(DATABASE)
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
            qr = qrcode.QRCode(
                version=1,
                box_size=10,
                border=4
            )

            qr.add_data(link)
            qr.make(fit=True)

            img = qr.make_image(
                fill_color="black",
                back_color="white"
            )

            filepath = os.path.join(GENERATED_FOLDER, "qr_code.png")
            img.save(filepath)

            qr_image = filepath

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
            filepath = os.path.join(GENERATED_FOLDER, filename)
            file.save(filepath)

            image = cv2.imread(filepath)

            if image is None:
                error = "Invalid image file."
            else:
                detector = cv2.QRCodeDetector()
                data, points, _ = detector.detectAndDecode(image)

                if data:
                    decoded_text = data
                else:
                    error = "Could not read QR code. Please upload a clear QR image."

    return render_template(
        "index.html",
        mode="qr_to_link",
        decoded_text=decoded_text,
        error=error,
        username=session.get("username")
    )


if __name__ == "__main__":
    app.run(debug=True)