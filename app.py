# app.py
import os, time, uuid, threading, sqlite3, random
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, send_file, flash
from flask_cors import CORS
import bcrypt
from werkzeug.utils import secure_filename

# import your cluster
from storage_virtual_network import StorageVirtualNetwork
from storage_virtual_node import StorageVirtualNode, TransferStatus

# CONFIG
DB = "app.db"
UPLOAD_DIR = "user_storage"
os.makedirs(UPLOAD_DIR, exist_ok=True)
USER_FREE_QUOTA = 2 * 1024**3  # 2GB free
OTP_TTL = 300  # seconds
BACKGROUND_POLL_INTERVAL = 1.0  # seconds for processing steps

app = Flask(__name__, template_folder="templates")
app.secret_key = os.getenv("FLASK_SECRET", "dev-secret")
CORS(app)

# ---------- DB helper ----------
def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

# ---------- Cluster init ----------
network = StorageVirtualNetwork()
def ensure_nodes():
    if len(network.nodes) == 0:
        n1 = StorageVirtualNode("node1", "10.0.0.1", cpu_capacity=4, memory_capacity=8, storage_capacity=20, bandwidth_mbps=100)
        n2 = StorageVirtualNode("node2", "10.0.0.2", cpu_capacity=4, memory_capacity=8, storage_capacity=20, bandwidth_mbps=100)
        n3 = StorageVirtualNode("node3", "10.0.0.3", cpu_capacity=2, memory_capacity=4, storage_capacity=10, bandwidth_mbps=50)
        network.add_node(n1); network.add_node(n2); network.add_node(n3)
        network.connect_nodes("node1","node2", bandwidth_mbps=100)
        network.connect_nodes("node2","node3", bandwidth_mbps=50)

ensure_nodes()

# in-memory mapping network_file_id -> local path metadata
FILES = {}

# ---------- OTP helpers ----------
def gen_otp():
    return f"{random.randint(100000,999999)}"

def store_otp(username, otp):
    expiry = time.time() + OTP_TTL
    conn = get_db(); cur = conn.cursor()
    cur.execute("INSERT OR REPLACE INTO otps (username, otp, expiry) VALUES (?, ?, ?)", (username, otp, expiry))
    conn.commit(); conn.close()

def validate_otp(username, otp):
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT otp, expiry FROM otps WHERE username=?", (username,))
    row = cur.fetchone()
    if not row:
        conn.close(); return False
    if time.time() > row[1]:
        cur.execute("DELETE FROM otps WHERE username=?", (username,)); conn.commit(); conn.close(); return False
    ok = (row[0] == otp)
    if ok:
        cur.execute("DELETE FROM otps WHERE username=?", (username,)); conn.commit()
    conn.close()
    return ok

# ---------- Auth routes ----------
@app.route("/signup", methods=["GET","POST"])
def signup():
    if request.method=="POST":
        username = request.form["username"].strip()
        email = request.form["email"].strip()
        password = request.form["password"]
        if not username or not password or not email:
            flash("Fill fields"); return redirect(url_for("signup"))
        pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        conn = get_db(); cur=conn.cursor()
        try:
            cur.execute("INSERT INTO users (username,email,password_hash,is_verified,extra_quota_bytes) VALUES (?,?,?,?,?)",
                        (username,email,pw_hash,0,0))
            conn.commit()
        except sqlite3.IntegrityError:
            conn.close(); flash("Username exists"); return redirect(url_for("signup"))
        conn.close()
        otp = gen_otp(); store_otp(username, otp)
        print(f"[DEV OTP] {username}: {otp}")
        session["pending_user"] = username
        return redirect(url_for("otp"))
    return render_template("signup.html")

@app.route("/otp", methods=["GET","POST"])
def otp():
    if request.method=="POST":
        username = session.get("pending_user")
        if not username: flash("No pending"); return redirect(url_for("login"))
        otp_input = request.form.get("otp")
        if validate_otp(username, otp_input):
            conn = get_db(); cur=conn.cursor(); cur.execute("UPDATE users SET is_verified=1 WHERE username=?", (username,)); conn.commit(); conn.close()
            session.pop("pending_user", None); flash("Verified. Login."); return redirect(url_for("login"))
        flash("Invalid OTP"); return render_template("otp.html")
    return render_template("otp.html")

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method=="POST":
        username = request.form["username"].strip()
        password = request.form["password"]
        conn = get_db(); cur=conn.cursor()
        cur.execute("SELECT id,password_hash,is_verified FROM users WHERE username=?", (username,))
        row = cur.fetchone()
        if not row or not bcrypt.checkpw(password.encode(), row[1].encode()):
            flash("Invalid credentials"); conn.close(); return redirect(url_for("login"))
        # produce OTP (extra security) then redirect to otp_login
        otp = gen_otp(); store_otp(username, otp); print(f"[DEV OTP] login {username}: {otp}")
        session["pending_user"] = username; session["pending_user_id"] = row[0]; conn.close(); return redirect(url_for("otp_login"))
    return render_template("login.html")

@app.route("/otp_login", methods=["GET","POST"])
def otp_login():
    if request.method=="POST":
        username = session.get("pending_user"); uid = session.get("pending_user_id")
        if not username: flash("No pending"); return redirect(url_for("login"))
        otp_input = request.form.get("otp")
        if validate_otp(username, otp_input):
            session.pop("pending_user", None); session.pop("pending_user_id", None)
            session["user_id"]=uid; session["username"]=username; flash("Logged in"); return redirect(url_for("dashboard"))
        flash("Invalid OTP"); return render_template("otp.html")
    return render_template("otp.html")

@app.route("/logout")
def logout():
    session.clear(); return redirect(url_for("login"))

# ---------- Dashboard & user file routes ----------
@app.route("/")
def dashboard():
    if "user_id" not in session: return redirect(url_for("login"))
    return render_template("drive.html")

def user_used_bytes(user_id):
    conn = get_db(); cur=conn.cursor(); cur.execute("SELECT SUM(size) FROM files WHERE user_id=?", (user_id,)); r=cur.fetchone(); conn.close(); return int(r[0] or 0)

def user_total_allowed(user_id):
    conn = get_db(); cur=conn.cursor(); cur.execute("SELECT extra_quota_bytes FROM users WHERE id=?", (user_id,)); r=cur.fetchone(); conn.close(); extra = int(r[0] or 0); return USER_FREE_QUOTA + extra

@app.route("/api/files", methods=["GET"])
def api_list_user_files():
    if "user_id" not in session: return jsonify({"error":"auth"}), 401
    uid = session["user_id"]
    conn = get_db(); cur=conn.cursor(); cur.execute("SELECT id,file_name,size,local_path,network_file_id,created_at FROM files WHERE user_id=? ORDER BY created_at DESC", (uid,)); rows=cur.fetchall(); conn.close()
    files = [dict(id=r[0], file_name=r[1], size=r[2], network_id=r[4], created_at=r[5]) for r in rows]
    used = user_used_bytes(uid); allowed = user_total_allowed(uid)
    return jsonify({"files":files, "used":used, "allowed":allowed})

@app.route("/api/upload", methods=["POST"])
def api_upload():
    if "user_id" not in session: return jsonify({"error":"auth"}), 401
    uid = session["user_id"]; username = session["username"]
    f = request.files.get("file")
    if not f: return jsonify({"error":"no_file"}), 400
    data = f.read(); size = len(data); f.stream.seek(0)
    allowed = user_total_allowed(uid); used = user_used_bytes(uid)
    if used + size > allowed: return jsonify({"error":"quota_exceeded","used":used,"allowed":allowed}), 403

    # local persist
    fid_local = uuid.uuid4().hex; secure = secure_filename(f.filename)
    local_path = os.path.join(UPLOAD_DIR, f"{fid_local}_{secure}")
    with open(local_path, "wb") as fh: fh.write(data)

    # initiate network transfer
    replication = int(request.form.get("replication", 2))
    source_node = request.form.get("source_node_id", "node1")
    tr = network.initiate_file_transfer(source_node_id=source_node, target_node_id=None, file_name=secure, file_size=size, replication_factor=replication)
    if not tr:
        os.remove(local_path)
        return jsonify({"error":"no_capacity"}), 507

    # store metadata in DB & FILES mapping
    conn = get_db(); cur=conn.cursor()
    cur.execute("INSERT INTO files (user_id,file_name,size,local_path,network_file_id,created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (uid, secure, size, local_path, tr.file_id, time.time()))
    conn.commit(); conn.close()
    FILES[tr.file_id] = {"local_path": local_path, "name": secure, "size": size, "owner": username, "created_at": time.time()}
    return jsonify({"file_id": tr.file_id, "chunks": len(tr.chunks), "status": tr.status.name})

@app.route("/api/download/<file_network_id>", methods=["GET"])
def api_download(file_network_id):
    # serve local copy saved at upload time
    info = FILES.get(file_network_id)
    if not info:
        # fallback: search DB
        conn = get_db(); cur=conn.cursor(); cur.execute("SELECT local_path, file_name FROM files WHERE network_file_id=?", (file_network_id,)); r=cur.fetchone(); conn.close()
        if not r: return jsonify({"error":"not_found"}), 404
        return send_file(r[0], as_attachment=True, download_name=r[1])
    return send_file(info["local_path"], as_attachment=True, download_name=info["name"])

@app.route("/api/delete/<file_network_id>", methods=["POST"])
def api_delete(file_network_id):
    if "user_id" not in session: return jsonify({"error":"auth"}), 401
    uid = session["user_id"]
    # check ownership
    conn = get_db(); cur=conn.cursor(); cur.execute("SELECT id, local_path, user_id FROM files WHERE network_file_id=?", (file_network_id,)); r=cur.fetchone()
    if not r: conn.close(); return jsonify({"error":"not_found"}), 404
    if r[2] != uid: conn.close(); return jsonify({"error":"forbidden"}), 403
    # delete local and db
    try: os.remove(r[1])
    except: pass
    cur.execute("DELETE FROM files WHERE id=?", (r[0],)); conn.commit(); conn.close()
    if file_network_id in FILES: del FILES[file_network_id]
    # TODO: propagate delete to cluster nodes
    return jsonify({"status":"deleted"})

# ---------- Network endpoints ----------
@app.get("/api/nodes")
def api_nodes():
    return jsonify(network.discover_nodes())

@app.post("/api/process_step")
def api_process_step():
    data = request.get_json() or {}
    source = data.get("source_node_id", "node1")
    fid = data.get("file_id")
    cps = int(data.get("chunks_per_step", 2))
    if fid:
        t,c = network.process_file_transfer(source_node_id=source, file_id=fid, chunks_per_step=cps)
        return jsonify({"transferred":t,"completed":c})
    else:
        results=[]
        for src, ops in list(network.transfer_operations.items()):
            for fid2 in list(ops.keys()):
                t,c = network.process_file_transfer(source_node_id=src, file_id=fid2, chunks_per_step=cps)
                results.append({"file_id":fid2,"transferred":t,"completed":c})
        return jsonify({"results":results})

@app.get("/api/file_status/<file_network_id>")
def api_file_status(file_network_id):
    # check nodes
    for n in network.nodes.values():
        if file_network_id in n.stored_files:
            return jsonify({"status":"stored","node":n.node_id})
    for ops in network.transfer_operations.values():
        if file_network_id in ops:
            tr = ops[file_network_id]
            return jsonify({"status":tr.status.name,"chunks_total":len(tr.chunks),"chunks_done":sum(1 for c in tr.chunks if c.status==TransferStatus.COMPLETED)})
    return jsonify({"status":"unknown"}), 404

# ---------- Admin ----------
@app.get("/admin")
def admin_panel():
    conn = get_db(); cur=conn.cursor()
    cur.execute("SELECT id, username, email, extra_quota_bytes FROM users")
    users = cur.fetchall(); conn.close()
    # format users
    ulist = [{"id":u[0],"username":u[1],"email":u[2],"extra_quota":u[3]} for u in users]
    return render_template("admin.html", users=ulist, network_stats=network.get_network_stats())

@app.post("/admin/add_quota")
def admin_add_quota():
    data = request.form
    uid = int(data.get("user_id"))
    add = int(data.get("add_bytes"))
    conn = get_db(); cur=conn.cursor()
    cur.execute("UPDATE users SET extra_quota_bytes=extra_quota_bytes + ? WHERE id=?", (add, uid)); conn.commit(); conn.close()
    return redirect(url_for("admin_panel"))

# ---------- Background worker to process transfers automatically ----------
def background_processor():
    while True:
        # process all transfers a bit
        for src, ops in list(network.transfer_operations.items()):
            for fid in list(ops.keys()):
                network.process_file_transfer(source_node_id=src, file_id=fid, chunks_per_step=2)
        time.sleep(BACKGROUND_POLL_INTERVAL)

bg_thread = threading.Thread(target=background_processor, daemon=True)
bg_thread.start()

# ---------- run app ----------
if __name__=="__main__":
    app.run(host="127.0.0.1", port=8000, debug=True)
