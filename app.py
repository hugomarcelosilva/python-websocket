from datetime import datetime, timedelta
from flask import Flask, jsonify, request, send_file, render_template
from flask_socketio import SocketIO
from repository.database import db
from db_models.payment import Payment
from payments.pix import Pix

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///database.db"
app.config["SECRET_KEY"] = "SECRET_KEY_WEBSOCKET"

db.init_app(app)
socketio = SocketIO(app)


@app.route("/payments/pix", methods=["POST"])
def create_payment_pix():
    data = request.get_json()

    if "value" not in data:
        return jsonify({"message": "Invalid payment data"}), 400

    expiration_date = datetime.now() + timedelta(minutes=30)

    new_payment = Payment(value=data["value"], expiration_date=expiration_date)

    pix_obj = Pix()
    data_payment_pix = pix_obj.create_payment()
    new_payment.bank_payment_id = data_payment_pix["bank_payment_id"]
    new_payment.qr_code = data_payment_pix["qr_code_path"]

    db.session.add(new_payment)
    db.session.commit()

    return jsonify(
        {"message": "The payment has been created!", "payment": new_payment.to_dict()}
    )


@app.route("/payments/pix/qr_code/<filename>", methods=["GET"])
def get_image(filename):
    return send_file(f"static/img/{filename}.png", mimetype="image/png")


@app.route("/payments/pix/confirmation", methods=["POST"])
def pix_confirmation():
    data = request.get_json()

    if "bank_payment_id" not in data and "value" not in data:
        return jsonify({"message": "Invalid payment data"}), 400

    payment = (
        db.session.query(Payment)
        .filter_by(bank_payment_id=data["bank_payment_id"])
        .first()
    )

    if not payment or payment.paid:
        return jsonify({"message": "Payment not found!"}), 404

    if data.get("value") != payment.value:
        return jsonify({"message": "Invalid payment data"}), 400

    payment.paid = True
    db.session.commit()
    socketio.emit(f"payment_confirmed_{payment.id}")

    return jsonify({"message": "The payment has been confirmed!"})


@app.route("/payments/pix/<int:payment_id>", methods=["GET"])
def payment_pix_page(payment_id):
    payment = db.session.get(Payment, payment_id)

    if not payment:
        return render_template("404.html")

    if payment.paid:
        return render_template(
            "confirmed_payment.html", payment_id=payment.id, value=payment.value
        )

    return render_template(
        "payment.html",
        payment_id=payment.id,
        value=payment.value,
        host="http://127.0.0.1:5000",
        qr_code=payment.qr_code,
    )


# Websockets
@socketio.on("connect")
def handle_connect():
    print("Client connected")


@socketio.on("disconnect")
def handle_disconnect():
    print("Client disconnected")


if __name__ == "__main__":
    socketio.run(app, debug=True)
