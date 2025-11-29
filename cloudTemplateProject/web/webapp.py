# webapp.py
from flask import Flask, render_template, request, redirect, url_for, session, flash
import grpc, cloudsecurity_pb2, cloudsecurity_pb2_grpc
import os

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET", "devsecret")

GRPC_SERVER = os.getenv("GRPC_SERVER", "localhost:51234")

def grpc_login(username, password):
    with grpc.insecure_channel(GRPC_SERVER) as channel:
        stub = cloudsecurity_pb2_grpc.UserServiceStub(channel)
        resp = stub.login(cloudsecurity_pb2.Request(login=username, password=password))
        return resp.result

@app.route("/")
def index():
    if "username" in session:
        return redirect(url_for("drive"))
    return render_template("login.html")

@app.route("/login", methods=["POST"])
def login():
    username = request.form.get("username")
    password = request.form.get("password")
    result = grpc_login(username, password)
    if result == "OTP_SENT":
        # store username temporarily in session for OTP verification
        session["pending_user"] = username
        flash("OTP sent. Check email (or console in dev).")
        return render_template("otp.html")
    elif result == "OK":
        session["username"] = username
        return redirect(url_for("drive"))
    else:
        flash("Invalid credentials")
        return redirect(url_for("index"))

@app.route("/verify_otp", methods=["POST"])
def verify_otp():
    username = session.get("pending_user")
    otp = request.form.get("otp")
    if not username:
        flash("No pending login")
        return redirect(url_for("index"))
    result = grpc_login(username, f"otp:{otp}")
    if result == "OK":
        session["username"] = username
        session.pop("pending_user", None)
        return redirect(url_for("drive"))
    else:
        flash("Invalid OTP")
        return render_template("otp.html")

@app.route("/drive")
def drive():
    if "username" not in session:
        return redirect(url_for("index"))
    # Here you would call your StorageVirtualNetwork REST endpoints to list files, upload, etc.
    # For now show a placeholder
    return render_template("drive.html", username=session["username"])

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))

if __name__ == "__main__":
    app.run(port=5000, debug=True)
