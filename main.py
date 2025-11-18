# app.py
from flask import Flask, jsonify, request
from storage_virtual_network import StorageVirtualNetwork
from storage_virtual_node import StorageVirtualNode
import threading
import time

app = Flask(__name__)

# In-memory network instance (for demo / local)
network = StorageVirtualNetwork()

# Helper to create example nodes (if none exist)
def ensure_example_nodes():
    if len(network.nodes) == 0:
        n1 = StorageVirtualNode("node1", "192.168.1.10", cpu_capacity=4, memory_capacity=16, storage_capacity=500, bandwidth=1000)
        n2 = StorageVirtualNode("node2", "192.168.1.11", cpu_capacity=8, memory_capacity=32, storage_capacity=1000, bandwidth=2000)
        network.add_node(n1)
        network.add_node(n2)
        network.connect_nodes("node1", "node2", bandwidth_mbps=1000)

ensure_example_nodes()

@app.route("/nodes", methods=["GET"])
def list_nodes():
    response = []
    for n in network.nodes.values():
        response.append({
            "node_id": n.node_id,
            "ip": n.ip_address,
            "alive": n.alive,
            "storage_used_bytes": n.used_storage,
            "storage_total_bytes": n.total_storage,
            "connections": list(n.connections.keys())
        })
    return jsonify(response)

@app.route("/discover", methods=["GET"])
def discover():
    return jsonify(network.discover_nodes())

@app.route("/stats", methods=["GET"])
def stats():
    return jsonify(network.get_network_stats())

@app.route("/initiate", methods=["POST"])
def initiate():
    """
    POST JSON:
    {
      "source_node_id": "node1",
      "target_node_id": "node2",    # optional
      "file_name": "file.zip",
      "file_size": 104857600,       # bytes
      "replication_factor": 2
    }
    """
    payload = request.json
    source = payload.get("source_node_id")
    target = payload.get("target_node_id")
    fname = payload.get("file_name")
    fsize = payload.get("file_size")
    rf = int(payload.get("replication_factor", 2))
    tr = network.initiate_file_transfer(source_node_id=source, target_node_id=target, file_name=fname, file_size=int(fsize), replication_factor=rf)
    if not tr:
        return jsonify({"error": "could not initiate transfer (no capacity/targets)"}), 400
    return jsonify({
        "file_id": tr.file_id,
        "file_name": tr.file_name,
        "total_size": tr.total_size,
        "chunks": len(tr.chunks),
        "status": tr.status.name
    })

@app.route("/process_step", methods=["POST"])
def process_step():
    """
    POST JSON:
    {
      "source_node_id": "node1",
      "file_id": "abcd1234",
      "chunks_per_step": 3
    }
    """
    payload = request.json
    source = payload.get("source_node_id")
    file_id = payload.get("file_id")
    cps = int(payload.get("chunks_per_step", 1))
    transferred, completed = network.process_file_transfer(source_node_id=source, file_id=file_id, chunks_per_step=cps)
    return jsonify({"transferred_chunks": transferred, "completed": completed})

@app.route("/simulate_fail", methods=["POST"])
def simulate_fail():
    """
    POST JSON:
    {
      "node_id": "node2",
      "alive": false
    }
    """
    payload = request.json
    node_id = payload.get("node_id")
    alive = payload.get("alive", False)
    if node_id not in network.nodes:
        return jsonify({"error": "unknown node"}), 404
    network.nodes[node_id].set_alive(bool(alive))
    return jsonify({"node_id": node_id, "alive": network.nodes[node_id].alive})

@app.route("/metrics/node/<node_id>", methods=["GET"])
def node_metrics(node_id):
    if node_id not in network.nodes:
        return jsonify({"error": "unknown node"}), 404
    n = network.nodes[node_id]
    return jsonify({
        "storage": n.get_storage_utilization(),
        "network": n.get_network_utilization(),
        "performance": n.get_performance_metrics()
    })

if __name__ == "__main__":
    app.run(port=8000, debug=True)
