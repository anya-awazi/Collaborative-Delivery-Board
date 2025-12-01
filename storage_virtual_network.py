# storage_virtual_network.py
from typing import Dict, List, Optional, Tuple
import hashlib
import time
from collections import defaultdict
from storage_virtual_node import StorageVirtualNode, FileTransfer, FileChunk, TransferStatus
import random
import threading

class StorageVirtualNetwork:
    def __init__(self):
        self.nodes: Dict[str, StorageVirtualNode] = {}
        self.nodes_by_ip: Dict[str, str] = {}
        self.transfer_operations: Dict[str, Dict[str, FileTransfer]] = defaultdict(dict)
        self._lock = threading.Lock()

    # node management
    def add_node(self, node: StorageVirtualNode):
        with self._lock:
            self.nodes[node.node_id] = node
            self.nodes_by_ip[node.ip_address] = node.node_id

    def remove_node(self, node_id: str):
        with self._lock:
            if node_id in self.nodes:
                ip = self.nodes[node_id].ip_address
                del self.nodes[node_id]
                if ip in self.nodes_by_ip:
                    del self.nodes_by_ip[ip]

    def discover_nodes(self) -> List[Dict]:
        with self._lock:
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

    def connect_nodes(self, node1_id: str, node2_id: str, bandwidth_mbps: int):
        with self._lock:
            if node1_id in self.nodes and node2_id in self.nodes:
                self.nodes[node1_id].add_connection(node2_id, bandwidth_mbps)
                self.nodes[node2_id].add_connection(node1_id, bandwidth_mbps)
                return True
            return False

    def _generate_file_id(self, file_name: str) -> str:
        return hashlib.md5(f"{file_name}-{time.time()}-{random.random()}".encode()).hexdigest()

    def initiate_file_transfer(
        self,
        source_node_id: str,
        target_node_id: Optional[str],
        file_name: str,
        file_size: int,
        replication_factor: int = 2
    ) -> Optional[FileTransfer]:
        with self._lock:
            if source_node_id not in self.nodes:
                return None

            file_id = self._generate_file_id(file_name)
            source_node = self.nodes[source_node_id]

            candidate_nodes = [n for n in self.nodes.values() if n.node_id != source_node_id and n.alive]
            candidate_nodes.sort(key=lambda n: (n.total_storage - n.used_storage), reverse=True)

            targets: List[StorageVirtualNode] = []
            if target_node_id and target_node_id in self.nodes and self.nodes[target_node_id].alive:
                t = self.nodes[target_node_id]
                if t.used_storage + file_size <= t.total_storage:
                    targets.append(t)

            for n in candidate_nodes:
                if len(targets) >= replication_factor:
                    break
                if n.node_id in [t.node_id for t in targets]:
                    continue
                if n.used_storage + file_size <= n.total_storage:
                    targets.append(n)

            if not targets:
                return None

            # initiate reservation on each target
            # store one representative transfer under source
            representative = None
            replication_ids = [t.node_id for t in targets]
            for t in targets:
                tr = t.initiate_file_transfer(file_id=file_id, file_name=file_name, file_size=file_size, source_node=source_node_id, replication_targets=replication_ids)
                if tr:
                    if representative is None:
                        representative = tr
                    # track each under source operations (last wins for same file_id)
                    self.transfer_operations[source_node_id][file_id] = tr

            return representative

    def _find_alternate_node_for_chunk(self, excluded_node_ids: List[str], file_size: int) -> Optional[StorageVirtualNode]:
        with self._lock:
            candidates = [n for n in self.nodes.values() if n.node_id not in excluded_node_ids and n.alive]
            candidates.sort(key=lambda n: (n.total_storage - n.used_storage), reverse=True)
            for c in candidates:
                if c.used_storage + file_size <= c.total_storage:
                    return c
            return None

    def process_file_transfer(
        self,
        source_node_id: str,
        file_id: str,
        chunks_per_step: int = 1
    ) -> Tuple[int, bool]:
        with self._lock:
            if source_node_id not in self.transfer_operations:
                return (0, False)
            transfers = self.transfer_operations[source_node_id]
            if file_id not in transfers:
                return (0, False)
            transfer = transfers[file_id]

        chunks_transferred = 0
        # replication targets from transfer object
        replication_target_ids = transfer.replication_targets or []
        if not replication_target_ids:
            with self._lock:
                replication_target_ids = [nid for nid, n in self.nodes.items() if file_id in n.active_transfers]

        # iterate chunks
        for chunk in transfer.chunks:
            if chunk.status == TransferStatus.COMPLETED:
                continue
            if chunks_transferred >= chunks_per_step:
                break

            success = False
            tried_nodes = []
            for target_id in list(replication_target_ids):
                tried_nodes.append(target_id)
                target_node = self.nodes.get(target_id)
                if not target_node:
                    continue
                res = target_node.process_chunk_transfer(file_id=file_id, chunk_id=chunk.chunk_id, source_node=source_node_id)
                if res:
                    chunk.status = TransferStatus.COMPLETED
                    chunk.stored_node = target_node.node_id
                    chunks_transferred += 1
                    success = True
                    break
                else:
                    alt = self._find_alternate_node_for_chunk(excluded_node_ids=tried_nodes + [source_node_id], file_size=chunk.size)
                    if alt:
                        alt_tr = alt.initiate_file_transfer(file_id=file_id, file_name=transfer.file_name, file_size=transfer.total_size, source_node=source_node_id, replication_targets=replication_target_ids)
                        if alt_tr:
                            replication_target_ids.append(alt.node_id)
                            res2 = alt.process_chunk_transfer(file_id=file_id, chunk_id=chunk.chunk_id, source_node=source_node_id)
                            if res2:
                                chunk.status = TransferStatus.COMPLETED
                                chunk.stored_node = alt.node_id
                                chunks_transferred += 1
                                success = True
                                break
            if not success:
                # leave chunk for next call
                continue

        # check completion
        if all(c.status == TransferStatus.COMPLETED for c in transfer.chunks):
            transfer.status = TransferStatus.COMPLETED
            transfer.completed_at = time.time()
            # note: nodes updated their used_storage on completion in node.process_chunk_transfer
            # remove from transfer_operations
            with self._lock:
                if file_id in self.transfer_operations.get(source_node_id, {}):
                    del self.transfer_operations[source_node_id][file_id]
            return (chunks_transferred, True)

        return (chunks_transferred, False)

    def get_network_stats(self) -> Dict[str, float]:
        with self._lock:
            total_bandwidth = sum(n.bandwidth for n in self.nodes.values())
            used_bandwidth = sum(n.network_utilization for n in self.nodes.values())
            total_storage = sum(n.total_storage for n in self.nodes.values())
            used_storage = sum(n.used_storage for n in self.nodes.values())
            return {
                "total_nodes": len(self.nodes),
                "total_bandwidth_bps": total_bandwidth,
                "used_bandwidth_bps": used_bandwidth,
                "bandwidth_utilization": (used_bandwidth / total_bandwidth) * 100 if total_bandwidth else 0.0,
                "total_storage_bytes": total_storage,
                "used_storage_bytes": used_storage,
                "storage_utilization": (used_storage / total_storage) * 100 if total_storage else 0.0,
                "active_transfers": sum(len(t) for t in self.transfer_operations.values())
            }
