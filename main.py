# main.py  (REWRITE + FULLY CORRECTED)
from flask import Flask, jsonify, request, render_template, send_file
from storage_virtual_network import StorageVirtualNetwork
from storage_virtual_node import StorageVirtualNode
from flask_cors import CORS
import os
import uuid

app = Flask(__name__)
CORS(app)

# -----------------------------------------
# INITIALIZE NETWORK
# -----------------------------------------
network = StorageVirtualNetwork()

def ensure_nodes():
    if len(network.nodes) == 0:
        n1 = StorageVirtualNode(
            "node1", "192.168.1.10",
            cpu_capacity=4, memory_capacity=16,
            storage_capacity=1024 * 1024 * 1024,   # 1GB
            bandwidth=1000
        )
        n2 = StorageVirtualNode(
            "node2", "192.168.1.11",
            cpu_capacity=8, memory_capacity=32,
            storage_capacity=1024 * 1024 * 1024,   # 1GB
            bandwidth=2000
        )
        network.add_node(n1)
        network.add_node(n2)
        network.connect_nodes("node1", "node2", bandwidth_mbps=1000)

ensure_nodes()

# Directory for uploaded user files
UPLOAD_DIR = "user_storage"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# -----------------------------------------
# FRONTEND DASHBOARD
# -----------------------------------------
@app.route("/")
def dashboard():
    return render_template("dashboard.html")

# -----------------------------------------
# USER API — STORAGE MANAGEMENT
# -----------------------------------------

# User free storage = 2GB
USER_FREE_LIMIT = 2 * 1024 * 1024 * 1024


def get_user_folder(username):
    path = os.path.join(UPLOAD_DIR, username)
    os.makedirs(path, exist_ok=True)
    return path


def calculate_storage_used(username):
    folder = get_user_folder(username)
    total = 0
    for f in os.listdir(folder):
        total += os.path.getsize(os.path.join(folder, f))
    return total


# Upload file
@app.route("/api/upload", methods=["POST"])
def upload_file():
    username = request.form.get("username")
    file = request.files.get("file")

    if not username or not file:
        return jsonify({"error": "username and file are required"}), 400

    used = calculate_storage_used(username)
    new_size = file.content_length or len(file.read())
    file.seek(0)

    if used + new_size > USER_FREE_LIMIT:
        return jsonify({"error": "Storage limit reached (2GB). Upgrade required."}), 403

    folder = get_user_folder(username)
    file_id = str(uuid.uuid4())
    filename = f"{file_id}_{file.filename}"
    filepath = os.path.join(folder, filename)
    file.save(filepath)

    return jsonify({
        "message": "uploaded",
        "file_id": file_id,
        "filename": file.filename,
        "size": new_size
    })


# Download file
@app.route("/api/download/<username>/<file_id>", methods=["GET"])
def download_file(username, file_id):
    folder = get_user_folder(username)

    for f in os.listdir(folder):
        if f.startswith(file_id):
            return send_file(os.path.join(folder, f), as_attachment=True)

    return jsonify({"error": "file not found"}), 404


# List files
@app.route("/api/files/<username>", methods=["GET"])
def list_files(username):
    folder = get_user_folder(username)
    files = []

    for f in os.listdir(folder):
        size = os.path.getsize(os.path.join(folder, f))
        file_id = f.split("_")[0]
        original_name = "_".join(f.split("_")[1:])
        files.append({
            "file_id": file_id,
            "filename": original_name,
            "size": size
        })

    used = calculate_storage_used(username)

    return jsonify({
        "files": files,
        "used_storage": used,
        "free_limit": USER_FREE_LIMIT,
        "remaining": USER_FREE_LIMIT - used
    })


# Delete file
@app.route("/api/delete", methods=["POST"])
def delete_file():
    data = request.json
    username = data.get("username")
    file_id = data.get("file_id")

    folder = get_user_folder(username)

    for f in os.listdir(folder):
        if f.startswith(file_id):
            os.remove(os.path.join(folder, f))
            return jsonify({"message": "deleted"})

    return jsonify({"error": "file not found"}), 404


# -----------------------------------------
# NODE SYSTEM (unchanged — your existing backend)
# -----------------------------------------
@app.route("/api/nodes")
def get_nodes():
    response = []
    for n in network.nodes.values():
        response.append({
            "node_id": n.node_id,
            "ip": n.ip_address,
            "alive": n.alive,
            "storage_used": n.used_storage,
            "storage_total": n.total_storage
        })
    return jsonify(response)


if __name__ == "__main__":
    app.run(port=8000, debug=True)
