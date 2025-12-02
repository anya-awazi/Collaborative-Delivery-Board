# main.py
from flask import Flask, jsonify, request, render_template, send_file
from flask_cors import CORS
import os
import uuid
import time

from storage_virtual_network import StorageVirtualNetwork
from storage_virtual_node import StorageVirtualNode

app = Flask(__name__, template_folder="templates")
CORS(app)

# -------------------------
# Storage network bootstrap
# -------------------------
network = StorageVirtualNetwork()

def ensure_example_nodes():
    # if network empty, create demo nodes
    if len(network.nodes) == 0:
        # NOTE: storage_capacity is in GB; bandwidth_mbps is passed to constructor
        n1 = StorageVirtualNode("node1", "192.168.1.10", cpu_capacity=4, memory_capacity=16, storage_capacity=500, bandwidth_mbps=1000)
        n2 = StorageVirtualNode("node2", "192.168.1.11", cpu_capacity=8, memory_capacity=32, storage_capacity=1000, bandwidth_mbps=2000)
        n3 = StorageVirtualNode("node3", "192.168.1.12", cpu_capacity=2, memory_capacity=4, storage_capacity=250, bandwidth_mbps=500)
        network.add_node(n1)
        network.add_node(n2)
        network.add_node(n3)

        # Connect nodes (bidirectional)
        network.connect_nodes("node1", "node2", bandwidth_mbps=1000)
        network.connect_nodes("node2", "node3", bandwidth_mbps=500)
        network.connect_nodes("node1", "node3", bandwidth_mbps=400)

ensure_example_nodes()

# -------------------------
# Local storage for uploaded bytes (so downloads work)
# -------------------------
USER_STORAGE_DIR = "user_storage"
os.makedirs(USER_STORAGE_DIR, exist_ok=True)

# Map network file_id -> metadata (local path, original name, size, owner)
FILES = {}  # file_id -> {path, name, size, owner, created_at}

# -------------------------
# Frontend / simple UI
# -------------------------
@app.get("/")
def ui_root():
    # existing template (drive.html / dashboard.html) should exist in templates/
    # fallback to a minimal page if not present
    if os.path.exists(os.path.join("templates", "drive.html")):
        return render_template("drive.html")
    return "<h3>Storage Network - API running. Use the provided frontend (templates/drive.html)</h3>"

# -------------------------
# Node & network endpoints
# -------------------------
@app.get("/api/nodes")
def api_nodes():
    return jsonify(network.discover_nodes())

@app.get("/api/network_stats")
def api_network_stats():
    return jsonify(network.get_network_stats())

@app.get("/api/node/<node_id>/metrics")
def api_node_metrics(node_id):
    if node_id not in network.nodes:
        return jsonify({"error": "unknown node"}), 404
    n = network.nodes[node_id]
    return jsonify({
        "storage": n.get_storage_utilization(),
        "network": n.get_network_utilization(),
        "performance": n.get_performance_metrics()
    })

@app.post("/api/simulate_fail")
def api_simulate_fail():
    """
    JSON: { "node_id": "node2", "alive": false }
    """
    data = request.get_json() or {}
    node_id = data.get("node_id")
    alive = data.get("alive", False)
    if node_id not in network.nodes:
        return jsonify({"error": "unknown node"}), 404
    network.nodes[node_id].set_alive(bool(alive))
    return jsonify({"node_id": node_id, "alive": network.nodes[node_id].alive})

# -------------------------
# File upload / transfer API
# -------------------------
@app.post("/api/upload")
def api_upload():
    """
    multipart/form-data:
      file -> file bytes
      source_node_id (optional) -> which node acts as source (defaults to node1)
      replication (optional) -> desired replication factor (int)
      owner (optional) -> username or id
    Returns network file_id (transfer id) if initiated
    """
    f = request.files.get("file")
    if not f:
        return jsonify({"error": "no file provided"}), 400

    try:
        replication = int(request.form.get("replication", 2))
    except Exception:
        replication = 2

    source_node = request.form.get("source_node_id", "node1")
    owner = request.form.get("owner", "anonymous")

    content = f.read()
    size = len(content)
    original_name = f.filename or f"file-{int(time.time())}"
    # persist locally so downloads work
    file_id_local = uuid.uuid4().hex
    local_path = os.path.join(USER_STORAGE_DIR, f"{file_id_local}_{original_name}")
    with open(local_path, "wb") as fh:
        fh.write(content)

    # initiate transfer in the simulated network
    tr = network.initiate_file_transfer(
        source_node_id=source_node,
        target_node_id=None,
        file_name=original_name,
        file_size=size,
        replication_factor=replication
    )

    if not tr:
        # cleanup local file if network could not accept
        try:
            os.remove(local_path)
        except Exception:
            pass
        return jsonify({"error": "no_capacity_or_targets"}), 507

    # store mapping using network transfer id
    FILES[tr.file_id] = {
        "local_path": local_path,
        "name": original_name,
        "size": size,
        "owner": owner,
        "created_at": time.time()
    }

    return jsonify({
        "file_id": tr.file_id,
        "file_name": tr.file_name,
        "size": tr.total_size,
        "chunks": len(tr.chunks),
        "status": tr.status.name
    })

@app.post("/api/process_step")
def api_process_step():
    """
    JSON: { "source_node_id": "node1", "file_id": "...", "chunks_per_step": 1 }
    If file_id is omitted, attempts to process all active transfers under given source.
    """
    data = request.get_json() or {}
    source = data.get("source_node_id", "node1")
    fid = data.get("file_id")
    cps = int(data.get("chunks_per_step", 1))

    if fid:
        transferred, completed = network.process_file_transfer(source_node_id=source, file_id=fid, chunks_per_step=cps)
        return jsonify({"transferred": transferred, "completed": completed})
    else:
        # attempt to process one step for every file under source (if any)
        results = []
        ops = list(network.transfer_operations.get(source, {}).items())
        for file_id, _ in ops:
            t, c = network.process_file_transfer(source_node_id=source, file_id=file_id, chunks_per_step=cps)
            results.append({"file_id": file_id, "transferred": t, "completed": c})
        return jsonify({"results": results})

@app.get("/api/file/<file_id>/status")
def api_file_status(file_id):
    # check stored files in nodes
    for node in network.nodes.values():
        if file_id in node.stored_files:
            return jsonify({"status": "stored", "node": node.node_id})
    # check active transfers
    for ops in network.transfer_operations.values():
        if file_id in ops:
            tr = ops[file_id]
            return jsonify({
                "status": tr.status.name,
                "chunks_total": len(tr.chunks),
                "chunks_completed": sum(1 for c in tr.chunks if c.status == TransferStatus.COMPLETED)
            })
    return jsonify({"status": "unknown"}), 404

# -------------------------
# File download / delete (serving the locally saved copy)
# -------------------------
@app.get("/api/download/<file_id>")
def api_download(file_id):
    info = FILES.get(file_id)
    if not info:
        return jsonify({"error": "file_not_found"}), 404
    return send_file(info["local_path"], as_attachment=True, download_name=info["name"])

@app.post("/api/delete/<file_id>")
def api_delete(file_id):
    info = FILES.get(file_id)
    if not info:
        return jsonify({"error": "file_not_found"}), 404
    # remove local file
    try:
        os.remove(info["local_path"])
    except Exception:
        pass
    del FILES[file_id]
    # NOTE: we do not yet call node.delete propagation in the simulated cluster
    return jsonify({"status": "deleted"})

# -------------------------
# helper: list files tracked by the server
# -------------------------
@app.get("/api/files")
def api_list_files():
    items = []
    for fid, meta in FILES.items():
        items.append({
            "file_id": fid,
            "name": meta["name"],
            "size": meta["size"],
            "owner": meta["owner"],
            "created_at": meta["created_at"]
        })
    return jsonify(items)

# -------------------------
# Run
# -------------------------
if __name__ == "__main__":
    print("Starting storage network UI at http://127.0.0.1:8000")
    app.run(host="127.0.0.1", port=8000, debug=True)
