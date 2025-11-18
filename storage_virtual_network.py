# storage_virtual_network.py
from typing import Dict, List, Optional, Tuple
import hashlib
import time
from collections import defaultdict
from storage_virtual_node import StorageVirtualNode, FileTransfer, FileChunk, TransferStatus
import random

class StorageVirtualNetwork:
    def __init__(self):
        self.nodes: Dict[str, StorageVirtualNode] = {}        # key: node_id
        self.nodes_by_ip: Dict[str, str] = {}                # ip -> node_id
        # transfer_operations[source_node_id][file_id] = FileTransfer (the "in-flight" transfer tracked by origin)
        self.transfer_operations: Dict[str, Dict[str, FileTransfer]] = defaultdict(dict)

    # ---------------- Node management / discovery ----------------
    def add_node(self, node: StorageVirtualNode):
        """Register a node with the network."""
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
    def connect_nodes(self, node1_id: str, node2_id: str, bandwidth_mbps: int):
        """Add bidirectional connection (bandwidth in Mbps)."""
        if node1_id in self.nodes and node2_id in self.nodes:
            self.nodes[node1_id].add_connection(node2_id, bandwidth_mbps)
            self.nodes[node2_id].add_connection(node1_id, bandwidth_mbps)
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
        if source_node_id not in self.nodes:
            return None

        # Generate unique file id
        file_id = hashlib.md5(f"{file_name}-{time.time()}".encode()).hexdigest()
        source_node = self.nodes[source_node_id]

        # Choose replication targets: prefer the target_node_id if given
        candidate_nodes = [n for n in self.nodes.values() if n.node_id != source_node_id and n.alive]
        # sort by available space descending
        candidate_nodes.sort(key=lambda n: (n.total_storage - n.used_storage), reverse=True)

        targets: List[StorageVirtualNode] = []
        if target_node_id:
            if target_node_id in self.nodes and self.nodes[target_node_id].alive:
                targets.append(self.nodes[target_node_id])
            else:
                # requested target not available
                pass

        # fill up to replication_factor
        for n in candidate_nodes:
            if n.node_id in [t.node_id for t in targets]:
                continue
            if len(targets) >= replication_factor:
                break
            # ensure node has capacity
            if n.used_storage + file_size <= n.total_storage:
                targets.append(n)

        # if no targets available
        if not targets:
            return None

        # Initiate transfer record on each target (replicas)
        transfers_per_target: List[FileTransfer] = []
        for t in targets:
            tr = t.initiate_file_transfer(file_id=file_id, file_name=file_name, file_size=file_size, source_node=source_node_id, replication_targets=[x.node_id for x in targets])
            if not tr:
                # skip nodes that could not reserve space
                continue
            transfers_per_target.append(tr)
            # track under source_node's transfer operations using the file_id
            self.transfer_operations[source_node_id][file_id] = tr

        if not transfers_per_target:
            return None

        # return the first transfer object as representative
        return transfers_per_target[0]

    def _find_alternate_node_for_chunk(self, excluded_node_ids: List[str], file_size: int) -> Optional[StorageVirtualNode]:
        """Find another node to accept a chunk when a target fails."""
        candidates = [n for n in self.nodes.values() if n.node_id not in excluded_node_ids and n.alive]
        # order by free space
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
        """
        Attempt to process chunks for a transfer initiated by source_node_id.
        This will attempt to deliver pending chunks to one of the replication targets.
        If a target node fails mid-transfer, transfer will be rerouted to another node.
        Returns (chunks_transferred, completed_flag)
        """
        if source_node_id not in self.transfer_operations:
            return (0, False)

        transfers = self.transfer_operations[source_node_id]
        if file_id not in transfers:
            return (0, False)

        transfer = transfers[file_id]
        chunks_transferred = 0

        # determine replication targets from transfer record if present
        replication_target_ids = transfer.replication_targets or []
        if not replication_target_ids:
            # fallback: find any node that has the file in its active transfers
            replication_target_ids = [nid for nid, n in self.nodes.items() if file_id in n.active_transfers]

     # iterate over each chunk and try to send it to all replication targets (one replica finished is ok)
        for chunk in transfer.chunks:
            if chunk.status == TransferStatus.COMPLETED:
                continue

            if chunks_transferred >= chunks_per_step:
                break

            # try each replication target in order until one accepts
            success = False
            tried_nodes = []
            for target_id in replication_target_ids:
                tried_nodes.append(target_id)
                if target_id not in self.nodes:
                    continue
                target_node = self.nodes[target_id]
                # simulate transfer to target
                res = target_node.process_chunk_transfer(file_id=file_id, chunk_id=chunk.chunk_id, source_node=source_node_id)
                if res:
                    # success, mark chunk as completed locally too
                    chunk.status = TransferStatus.COMPLETED
                    chunk.stored_node = target_node.node_id
                    chunks_transferred += 1
                    success = True
                    break
                else:
                    # if target_node failed or could not accept chunk, try alternate
                    # attempt reroute: look for another node with capacity
                    alt = self._find_alternate_node_for_chunk(excluded_node_ids=tried_nodes + [source_node_id], file_size=chunk.size)
                    if alt:
                        # register transfer reservation on alt if needed
                        alt_tr = alt.initiate_file_transfer(file_id=file_id, file_name=transfer.file_name, file_size=transfer.total_size, source_node=source_node_id, replication_targets=replication_target_ids)
                        if alt_tr:
                            # add alt to replication targets so next iteration tries it directly
                            replication_target_ids.append(alt.node_id)
                            self.nodes[target_id] = target_node  # no-op but ensure presence
                            # attempt to send to alt
                            res2 = alt.process_chunk_transfer(file_id=file_id, chunk_id=chunk.chunk_id, source_node=source_node_id)
                            if res2:
                                chunk.status = TransferStatus.COMPLETED
                                chunk.stored_node = alt.node_id
                                chunks_transferred += 1
                                success = True
                                break
                            else:
                                # alt failed too; continue searching
                                continue
                        else:
                            continue
                    else:
                        continue

            if not success:
                # we could not transfer this chunk in this step
                # don't mark it failed globally yet; allow retries in next call
                continue

        # after processing, check transfer completion: all chunks marked completed
        if all(c.status == TransferStatus.COMPLETED for c in transfer.chunks):
            transfer.status = TransferStatus.COMPLETED
            transfer.completed_at = time.time()
            # update network-wide bookkeeping: increase used storage on nodes which stored the file
            for n in self.nodes.values():
                if file_id in n.stored_files:
                    # node already accounted for used storage
                    continue
            # remove from transfer_operations
            if file_id in self.transfer_operations[source_node_id]:
                del self.transfer_operations[source_node_id][file_id]
            return (chunks_transferred, True)

        return (chunks_transferred, False)

    def get_network_stats(self) -> Dict[str, float]:
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