from typing import Dict, List, Optional, Tuple
import hashlib
import time
from storage_virtual_node import StorageVirtualNode, FileTransfer,FileChunk, TransferStatus
from collections import defaultdict
import random 

class StorageVirtualNetwork:
    def __init__(self):
        self.nodes: Dict[str, StorageVirtualNode] = {}
        self.nodes_by_ip: Dict[str, str] = {}
        self.transfer_operations: Dict[str, Dict[str, FileTransfer]] = defaultdict(dict)

     # ---------------- Node management / discovery ----------------   
    def add_node(self, node: StorageVirtualNode):
        """Add a node to the network"""
        self.nodes[node.node_id] = node
        self.nodes_by_ip[node.ip_address] = node.node_id

    def remove_node(self, node_id: str):
        if node_id in self.nodes:
            ip = self.nodes[node_id].ip_address
            del self.nodes[node_id]
            if ip in self.nodes_by_ip:
                del self.nodes_by_ip[ip]   

    def discover_nodes(self) -> List[Dict]:
        """Return a list of node metadata (discovery)."""
        return [
            {
                "node_id": n.node_id,
                "ip": n.ip_address,
                "alive": n.alive,
                "storage_total": n.total_storage,
                "storage_used": n.used_storage
            }
            for n in self.nodes.values()
        ] 
    
    
    # ---------------- Connectivity ----------------    
    def connect_nodes(self, node1_id: str, node2_id: str, bandwidth: int):
        """Connect two nodes with specified bandwidth"""
        if node1_id in self.nodes and node2_id in self.nodes:
            self.nodes[node1_id].add_connection(node2_id, bandwidth)
            self.nodes[node2_id].add_connection(node1_id, bandwidth)
            return True
        return False
    

# ---------------- Transfer and replication ----------------
    def initiate_file_transfer(
        self,
        source_node_id: str,
        target_node_id: Optional[str],
        file_name: str,
        file_size: int,
        replication_factor: int = 2
    ) -> Optional[FileTransfer]:
        """
        Initiate a file transfer from source node to target node.
        If target_node_id is None, pick best node(s) automatically.
        replication_factor defines how many replicas to create (including primary).
        """
        if source_node_id not in self.nodes or target_node_id not in self.nodes:
            return None
            
        # Generate unique file ID
        file_id = hashlib.md5(f"{file_name}-{time.time()}".encode()).hexdigest()
        
        # Request storage on target node
        target_node = self.nodes[target_node_id]
        transfer = target_node.initiate_file_transfer(file_id, file_name, file_size, source_node_id)
        
        if transfer:
            self.transfer_operations[source_node_id][file_id] = transfer
            return transfer
        return None
    
    def process_file_transfer(
        self,
        source_node_id: str,
        target_node_id: str,
        file_id: str,
        chunks_per_step: int = 1
    ) -> Tuple[int, bool]:
        """Process a file transfer in chunks"""
        if (source_node_id not in self.nodes or 
            target_node_id not in self.nodes or
            file_id not in self.transfer_operations[source_node_id]):
            return (0, False)
            
        source_node = self.nodes[source_node_id]
        target_node = self.nodes[target_node_id]
        transfer = self.transfer_operations[source_node_id][file_id]
        
        chunks_transferred = 0
        for chunk in transfer.chunks:
            if chunk.status != TransferStatus.COMPLETED and chunks_transferred < chunks_per_step:
                if target_node.process_chunk_transfer(file_id, chunk.chunk_id, source_node_id):
                    chunks_transferred += 1
                else:
                    return (chunks_transferred, False)
        
        # Check if transfer is complete
        if transfer.status == TransferStatus.COMPLETED:
            del self.transfer_operations[source_node_id][file_id]
            return (chunks_transferred, True)
            
        return (chunks_transferred, False)
    
    def get_network_stats(self) -> Dict[str, float]:
        """Get overall network statistics"""
        total_bandwidth = sum(n.bandwidth for n in self.nodes.values())
        used_bandwidth = sum(n.network_utilization for n in self.nodes.values())
        total_storage = sum(n.total_storage for n in self.nodes.values())
        used_storage = sum(n.used_storage for n in self.nodes.values())
        
        return {
            "total_nodes": len(self.nodes),
            "total_bandwidth_bps": total_bandwidth,
            "used_bandwidth_bps": used_bandwidth,
            "bandwidth_utilization": (used_bandwidth / total_bandwidth) * 100,
            "total_storage_bytes": total_storage,
            "used_storage_bytes": used_storage,
            "storage_utilization": (used_storage / total_storage) * 100,
            "active_transfers": sum(len(t) for t in self.transfer_operations.values())
        }