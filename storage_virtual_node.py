# storage_virtual_node.py
import time
import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Union
from enum import Enum, auto
import hashlib
import threading

class TransferStatus(Enum):
    PENDING = auto()
    IN_PROGRESS = auto()
    COMPLETED = auto()
    FAILED = auto()

@dataclass
class FileChunk:
    chunk_id: int
    size: int  # in bytes
    checksum: str
    status: TransferStatus = TransferStatus.PENDING
    stored_node: Optional[str] = None

@dataclass
class FileTransfer:
    file_id: str
    file_name: str
    total_size: int  # in bytes
    chunks: List[FileChunk]
    status: TransferStatus = TransferStatus.PENDING
    created_at: float = None
    completed_at: Optional[float] = None
    replication_targets: Optional[List[str]] = None  # nodes storing replicas

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = time.time()

class StorageVirtualNode:
    def __init__(
        self,
        node_id: str,
        ip_address: str,
        cpu_capacity: int,  # in vCPUs
        memory_capacity: int,  # in GB
        storage_capacity: int,  # in GB
        bandwidth_mbps: int  # in Mbps
    ):
        self.node_id = node_id
        self.ip_address = ip_address
        self.cpu_capacity = cpu_capacity
        self.memory_capacity = memory_capacity
        self.total_storage = int(storage_capacity * 1024 * 1024 * 1024)  # bytes
        self.bandwidth = int(bandwidth_mbps * 1_000_000)  # bits per second

        # Current utilization
        self.used_storage = 0
        self.active_transfers: Dict[str, FileTransfer] = {}
        self.stored_files: Dict[str, FileTransfer] = {}
        self.network_utilization = 0.0  # current used bps

        # Performance metrics
        self.total_requests_processed = 0
        self.total_data_transferred = 0  # bytes
        self.failed_transfers = 0

        # Network connections (node_id -> bandwidth_bps)
        self.connections: Dict[str, int] = {}

        # Node state
        self.alive = True

        # thread-safety
        self._lock = threading.Lock()

    def set_alive(self, alive: bool):
        with self._lock:
            self.alive = bool(alive)

    def add_connection(self, node_id: str, bandwidth_mbps: int):
        with self._lock:
            self.connections[node_id] = int(bandwidth_mbps * 1_000_000)

    def _calculate_chunk_size(self, file_size: int) -> int:
        if file_size < 10 * 1024**2:
            return 512 * 1024
        elif file_size < 100 * 1024**2:
            return 2 * 1024**2
        else:
            return 10 * 1024**2

    def _generate_chunks(self, file_id: str, file_size: int) -> List[FileChunk]:
        chunk_size = self._calculate_chunk_size(file_size)
        num_chunks = math.ceil(file_size / chunk_size)
        chunks = []
        for i in range(num_chunks):
            csize = min(chunk_size, file_size - i * chunk_size)
            checksum = hashlib.md5(f"{file_id}-{i}".encode()).hexdigest()
            chunks.append(FileChunk(chunk_id=i, size=csize, checksum=checksum))
        return chunks

    def initiate_file_transfer(
        self,
        file_id: str,
        file_name: str,
        file_size: int,
        source_node: Optional[str] = None,
        replication_targets: Optional[List[str]] = None
    ) -> Optional[FileTransfer]:
        with self._lock:
            if self.used_storage + file_size > self.total_storage:
                return None
            chunks = self._generate_chunks(file_id, file_size)
            tr = FileTransfer(
                file_id=file_id,
                file_name=file_name,
                total_size=file_size,
                chunks=chunks,
                replication_targets=replication_targets or []
            )
            self.active_transfers[file_id] = tr
            return tr

    def process_chunk_transfer(
        self,
        file_id: str,
        chunk_id: int,
        source_node: str
    ) -> bool:
        with self._lock:
            if not self.alive:
                self.failed_transfers += 1
                return False
            if file_id not in self.active_transfers:
                return False
            transfer = self.active_transfers[file_id]

            # find chunk
            chunk = next((c for c in transfer.chunks if c.chunk_id == chunk_id), None)
            if chunk is None:
                return False

            available_bandwidth = min(
                max(0, self.bandwidth - self.network_utilization),
                self.connections.get(source_node, 0)
            )
            if available_bandwidth <= 0:
                return False

            # simulate transfer time but limit to 0.5s to keep UI responsive
            chunk_size_bits = chunk.size * 8
            transfer_time = chunk_size_bits / float(available_bandwidth) if available_bandwidth > 0 else 0.01
            time.sleep(min(transfer_time, 0.5))

            # mark chunk done
            chunk.status = TransferStatus.COMPLETED
            chunk.stored_node = self.node_id

            # metrics
            util_bps = available_bandwidth * 0.8
            self.network_utilization += util_bps
            self.total_data_transferred += chunk.size

            # finalize
            if all(c.status == TransferStatus.COMPLETED for c in transfer.chunks):
                transfer.status = TransferStatus.COMPLETED
                transfer.completed_at = time.time()
                self.used_storage += transfer.total_size
                self.stored_files[file_id] = transfer
                del self.active_transfers[file_id]
                self.total_requests_processed += 1
            return True

    def retrieve_file(self, file_id: str) -> Optional[FileTransfer]:
        with self._lock:
            if file_id not in self.stored_files:
                return None
            f = self.stored_files[file_id]
            new_chunks = [FileChunk(chunk_id=c.chunk_id, size=c.size, checksum=c.checksum) for c in f.chunks]
            return FileTransfer(file_id=f.file_id, file_name=f.file_name, total_size=f.total_size, chunks=new_chunks)

    def get_storage_utilization(self) -> Dict[str, Union[int, float]]:
        with self._lock:
            return {
                "used_bytes": self.used_storage,
                "total_bytes": self.total_storage,
                "utilization_percent": (self.used_storage / self.total_storage) * 100 if self.total_storage else 0.0,
                "files_stored": len(self.stored_files),
                "active_transfers": len(self.active_transfers),
                "alive": self.alive
            }

    def get_network_utilization(self) -> Dict[str, Union[int, float, List[str]]]:
        with self._lock:
            return {
                "current_utilization_bps": self.network_utilization,
                "max_bandwidth_bps": self.bandwidth,
                "utilization_percent": (self.network_utilization / self.bandwidth) * 100 if self.bandwidth else 0.0,
                "connections": list(self.connections.keys())
            }

    def get_performance_metrics(self) -> Dict[str, int]:
        with self._lock:
            return {
                "total_requests_processed": self.total_requests_processed,
                "total_data_transferred_bytes": self.total_data_transferred,
                "failed_transfers": self.failed_transfers,
                "current_active_transfers": len(self.active_transfers)
            }
