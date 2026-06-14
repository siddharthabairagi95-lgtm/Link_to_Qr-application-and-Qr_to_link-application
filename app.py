from flask import Flask, render_template, request
import qrcode
import os
import cv2
from werkzeug.utils import secure_filename

app = Flask(__name__)

GENERATED_FOLDER = "static/generated"
os.makedirs(GENERATED_FOLDER, exist_ok=True)


@app.route("/")
def home():
    return render_template("index.html", mode=None)


@app.route("/link-to-qr", methods=["GET", "POST"])
def link_to_qr():
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
        error=error
    )


@app.route("/qr-to-link", methods=["GET", "POST"])
def qr_to_link():
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
        error=error
    )


if __name__ == "__main__":
    app.run(debug=True)