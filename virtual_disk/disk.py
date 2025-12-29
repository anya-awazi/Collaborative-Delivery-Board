import os
import struct
import time
import json
from dataclasses import dataclass, asdict, field
from enum import Enum, IntEnum
from typing import Dict, List, Optional, Set, BinaryIO, Tuple, Union
import hashlib

# Constants
BLOCK_SIZE = 4096  # 4KB blocks
MAGIC_NUMBER = b'CLOUDDISK'
VERSION = 1
METADATA_BLOCKS = 16  # Number of blocks reserved for metadata
MAX_FILENAME_LENGTH = 255
MAX_PATH_LENGTH = 4096

# File types
class FileType(Enum):
    REGULAR = 1
    DIRECTORY = 2
    SYMLINK = 3

# File permissions (Unix-style)
class Permission(IntEnum):
    READ = 0o4
    WRITE = 0o2
    EXECUTE = 0o1
    ALL = 0o7

@dataclass
class Inode:
    """Inode structure for file metadata."""
    file_type: FileType
    size: int = 0
    blocks: List[int] = field(default_factory=list)
    permissions: int = 0o644  # Default permissions: rw-r--r--
    uid: int = 0  # User ID
    gid: int = 0  # Group ID
    atime: float = field(default_factory=time.time)  # Last access
    mtime: float = field(default_factory=time.time)  # Last modification
    ctime: float = field(default_factory=time.time)  # Creation time
    nlink: int = 1  # Number of hard links
    
    def to_bytes(self) -> bytes:
        """Serialize inode to bytes."""
        data = {
            'file_type': self.file_type.value,
            'size': self.size,
            'blocks': self.blocks,
            'permissions': self.permissions,
            'uid': self.uid,
            'gid': self.gid,
            'atime': self.atime,
            'mtime': self.mtime,
            'ctime': self.ctime,
            'nlink': self.nlink
        }
        json_str = json.dumps(data).encode('utf-8')
        # Pad to BLOCK_SIZE
        return json_str.ljust(BLOCK_SIZE, b'\0')
    
    @classmethod
    def from_bytes(cls, data: bytes) -> 'Inode':
        """Deserialize inode from bytes."""
        try:
            json_str = data.rstrip(b'\0').decode('utf-8')
            data = json.loads(json_str)
            inode = cls(
                file_type=FileType(data['file_type']),
                size=data['size'],
                blocks=data['blocks'],
                permissions=data['permissions'],
                uid=data['uid'],
                gid=data['gid'],
                atime=data['atime'],
                mtime=data['mtime'],
                ctime=data['ctime'],
                nlink=data['nlink']
            )
            return inode
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            raise ValueError(f"Invalid inode data: {e}")

class DirectoryEntry:
    """Directory entry structure."""
    def __init__(self, name: str, inode_num: int):
        self.name = name
        self.inode_num = inode_num
    
    def to_bytes(self) -> bytes:
        """Serialize directory entry to bytes."""
        name_encoded = self.name.encode('utf-8')
        if len(name_encoded) > MAX_FILENAME_LENGTH:
            raise ValueError(f"Filename too long: {self.name}")
        
        # Format: [4 bytes name length][name][8 bytes inode number]
        return struct.pack(f'!I{len(name_encoded)}sQ', 
                         len(name_encoded), name_encoded, self.inode_num)
    
    @classmethod
    def from_bytes(cls, data: bytes) -> 'DirectoryEntry':
        """Deserialize directory entry from bytes."""
        name_len = struct.unpack('!I', data[:4])[0]
        name = data[4:4+name_len].decode('utf-8')
        inode_num = struct.unpack('!Q', data[4+name_len:4+name_len+8])[0]
        return cls(name, inode_num)
    
    @classmethod
    def entry_size(cls, name: str) -> int:
        """Calculate the size of a directory entry in bytes."""
        return 4 + len(name.encode('utf-8')) + 8

class VirtualDisk:
    """
    A virtual disk with a simple file system implementation.
    
    The disk is organized as follows:
    - Block 0: Superblock (magic, version, metadata)
    - Blocks 1-15: Inode table and block allocation bitmap
    - Remaining blocks: Data blocks
    """
    
    def __init__(self, disk_path: str, size_mb: int = 100, create: bool = False):
        """
        Initialize or create a virtual disk.
        
        Args:
            disk_path: Path to the disk file
            size_mb: Size of the disk in MB (only used when creating)
            create: If True, create a new disk
        """
        self.disk_path = disk_path
        self.size_mb = size_mb
        self.block_count = (size_mb * 1024 * 1024) // BLOCK_SIZE
        self.free_blocks: Set[int] = set()
        self.used_blocks: Set[int] = set()
        self.inodes: Dict[int, Inode] = {}
        self.next_inode = 2  # Inode 1 is root directory
        self.lock = None  # For thread safety (to be implemented)
        
        if create:
            self._create_disk()
        else:
            self._load_disk()
    
    def _create_disk(self) -> None:
        """Create a new virtual disk with empty file system."""
        if os.path.exists(self.disk_path):
            raise FileExistsError(f"Disk file {self.disk_path} already exists")
            
        # Initialize disk with zeros
        with open(self.disk_path, 'wb') as f:
            f.truncate(self.block_count * BLOCK_SIZE)
        
        # Initialize free blocks (all blocks except metadata)
        self.free_blocks = set(range(METADATA_BLOCKS, self.block_count))
        self.used_blocks = set(range(METADATA_BLOCKS))
        
        # Create root directory inode
        root_inode = Inode(
            file_type=FileType.DIRECTORY,
            permissions=0o755,
            uid=0,
            gid=0,
            ctime=time.time(),
            mtime=time.time(),
            atime=time.time()
        )
        self.inodes[1] = root_inode
        
        # Write initial metadata
        self._write_metadata()
        
        # Create standard directories
        self._create_standard_directories()
    
    def _create_standard_directories(self) -> None:
        """Create standard directories (like /tmp, /home, etc.)."""
        std_dirs = ['tmp', 'home', 'etc', 'var', 'bin']
        for dirname in std_dirs:
            try:
                self.create_file(f'/{dirname}', file_type=FileType.DIRECTORY)
            except FileExistsError:
                pass
    
    def _load_disk(self) -> None:
        """Load an existing virtual disk."""
        if not os.path.exists(self.disk_path):
            raise FileNotFoundError(f"Disk file {self.disk_path} not found")
            
        # Verify file size
        size = os.path.getsize(self.disk_path)
        if size % BLOCK_SIZE != 0:
            raise ValueError(f"Invalid disk size: {size} is not a multiple of {BLOCK_SIZE}")
            
        self.block_count = size // BLOCK_SIZE
        
        # Read superblock
        with open(self.disk_path, 'rb') as f:
            # Read and verify magic number
            magic = f.read(len(MAGIC_NUMBER))
            if magic != MAGIC_NUMBER:
                raise ValueError("Invalid disk format: bad magic number")
                
            # Read version
            version = struct.unpack('!I', f.read(4))[0]
            if version != VERSION:
                raise ValueError(f"Unsupported disk version: {version}")
            
            # Read metadata
            self._read_metadata()
    
    def _write_metadata(self) -> None:
        """Write all metadata to disk."""
        with open(self.disk_path, 'r+b') as f:
            # Write superblock
            f.write(MAGIC_NUMBER)  # 8 bytes
            f.write(struct.pack('!I', VERSION))  # 4 bytes
            f.write(struct.pack('!QQQ', 
                self.block_count,  # Total blocks
                len(self.free_blocks),  # Free blocks count
                self.next_inode  # Next available inode number
            ))  # 24 bytes
            
            # Write inode table
            inode_table_offset = BLOCK_SIZE  # Start after superblock
            f.seek(inode_table_offset)
            
            # Write number of inodes
            f.write(struct.pack('!Q', len(self.inodes)))  # 8 bytes
            
            # Write each inode
            for inode_num, inode in sorted(self.inodes.items()):
                f.write(struct.pack('!Q', inode_num))  # Inode number
                f.write(inode.to_bytes())  # Inode data
            
            # Write block allocation bitmap
            bitmap_offset = inode_table_offset + BLOCK_SIZE  # Next block after inode table
            f.seek(bitmap_offset)
            
            # Initialize bitmap (1 bit per block)
            bitmap_size = (self.block_count + 7) // 8  # Round up to nearest byte
            bitmap = bytearray(bitmap_size)
            
            # Set bits for used blocks
            for block in self.used_blocks:
                byte = block // 8
                bit = block % 8
                bitmap[byte] |= (1 << bit)
            
            f.write(bitmap)
            f.flush()
    
    def _read_metadata(self) -> None:
        """Read metadata from disk."""
        with open(self.disk_path, 'rb') as f:
            # Skip superblock (already verified)
            f.seek(len(MAGIC_NUMBER) + 4)  # Skip magic + version
            
            # Read disk metadata
            self.block_count, free_count, self.next_inode = struct.unpack('!QQQ', f.read(24))
            
            # Read inode table
            inode_count = struct.unpack('!Q', f.read(8))[0]
            self.inodes = {}
            
            for _ in range(inode_count):
                inode_num = struct.unpack('!Q', f.read(8))[0]
                inode_data = f.read(BLOCK_SIZE)
                self.inodes[inode_num] = Inode.from_bytes(inode_data)
            
            # Read block allocation bitmap
            self.used_blocks = set()
            self.free_blocks = set()
            
            # Skip to bitmap
            f.seek(BLOCK_SIZE)  # Skip to block 1 (after superblock)
            inode_count = struct.unpack('!Q', f.read(8))[0]  # Read inode count again
            f.seek(BLOCK_SIZE + 8 + (inode_count * (8 + BLOCK_SIZE)))  # Skip inode table
            
            # Read bitmap
            bitmap_size = (self.block_count + 7) // 8
            bitmap = f.read(bitmap_size)
            
            # Parse bitmap
            for byte_idx in range(len(bitmap)):
                byte = bitmap[byte_idx]
                for bit in range(8):
                    block_num = (byte_idx * 8) + bit
                    if block_num >= self.block_count:
                        break
                    
                    if byte & (1 << bit):
                        self.used_blocks.add(block_num)
                    else:
                        self.free_blocks.add(block_num)
    
    def create_file(self, path: str, content: bytes = None, 
                   file_type: FileType = FileType.REGULAR, 
                   permissions: int = 0o644) -> int:
        """
        Create a new file or directory.
        
        Args:
            path: File path (must be absolute)
            content: File content (for regular files)
            file_type: Type of file to create
            permissions: File permissions (Unix-style)
            
        Returns:
            Inode number of the created file
        """
        if not path.startswith('/'):
            raise ValueError("Path must be absolute")
        
        # Split path into directory and filename
        dirname, basename = os.path.split(path)
        if not basename:
            raise ValueError("Invalid path")
        
        # Get parent directory inode
        parent_inode = self._path_to_inode(dirname)
        if not parent_inode or parent_inode.file_type != FileType.DIRECTORY:
            raise NotADirectoryError(f"Not a directory: {dirname}")
        
        # Check if file already exists
        try:
            existing = self._lookup(parent_inode, basename)
            raise FileExistsError(f"File exists: {path}")
        except FileNotFoundError:
            pass
        
        # Create new inode
        inode_num = self.next_inode
        self.next_inode += 1
        
        inode = Inode(
            file_type=file_type,
            permissions=permissions,
            uid=0,  # TODO: Get current user ID
            gid=0,  # TODO: Get current group ID
            ctime=time.time(),
            mtime=time.time(),
            atime=time.time(),
            size=0
        )
        
        # For regular files, write content
        if file_type == FileType.REGULAR and content:
            self._write_data(inode, content)
        # For directories, add . and .. entries
        elif file_type == FileType.DIRECTORY:
            # Allocate a block for the directory entries
            block_num = self._allocate_blocks(1)[0]
            inode.blocks = [block_num]
            
            # Create . and .. entries
            entries = [
                DirectoryEntry('.', inode_num).to_bytes(),
                DirectoryEntry('..', self._get_inode_number(parent_inode)).to_bytes()
            ]
            
            # Write directory entries to block
            with open(self.disk_path, 'r+b') as f:
                f.seek(block_num * BLOCK_SIZE)
                f.write(b''.join(entries))
            
            inode.size = len(b''.join(entries))
        
        # Add directory entry
        self._add_dirent(parent_inode, basename, inode_num)
        
        # Update inode
        self.inodes[inode_num] = inode
        
        # Update metadata
        self._write_metadata()
        
        return inode_num
    
    def read_file(self, path: str) -> bytes:
        """
        Read the contents of a file.
        
        Args:
            path: Path to the file
            
        Returns:
            File content as bytes
        """
        inode = self._path_to_inode(path)
        if not inode or inode.file_type != FileType.REGULAR:
            raise FileNotFoundError(f"File not found: {path}")
        
        # Update access time
        inode.atime = time.time()
        self._write_metadata()
        
        return self._read_data(inode)
    
    def write_file(self, path: str, content: bytes, append: bool = False) -> int:
        """
        Write content to a file, creating it if it doesn't exist.
        
        Args:
            path: Path to the file
            content: Content to write
            append: If True, append to existing content
            
        Returns:
            Number of bytes written
        """
        try:
            inode = self._path_to_inode(path)
            if inode.file_type != FileType.REGULAR:
                raise IsADirectoryError(f"Is a directory: {path}")
            
            if append:
                existing_content = self._read_data(inode)
                content = existing_content + content
        except FileNotFoundError:
            # Create new file
            inode_num = self.create_file(path, content)
            inode = self.inodes[inode_num]
        
        # Write data
        bytes_written = self._write_data(inode, content)
        
        # Update modification time
        inode.mtime = time.time()
        self._write_metadata()
        
        return bytes_written
    
    def delete_file(self, path: str, recursive: bool = False) -> bool:
        """
        Delete a file or directory.
        
        Args:
            path: Path to the file or directory
            recursive: If True, delete directories recursively
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Get the inode of the file to delete
            inode = self._path_to_inode(path)
            inode_num = self._get_inode_number(inode)
            
            # Handle directories
            if inode.file_type == FileType.DIRECTORY:
                if not recursive:
                    # Check if directory is empty (except . and ..)
                    entries = self._read_dir_entries(inode)
                    if len(entries) > 2:  # More than . and ..
                        raise OSError(f"Directory not empty: {path}")
                else:
                    # Recursively delete contents
                    entries = self._read_dir_entries(inode)
                    for entry in entries:
                        if entry.name not in ('.', '..'):
                            self.delete_file(os.path.join(path, entry.name), True)
            
            # Remove directory entry
            dirname, basename = os.path.split(path)
            parent_inode = self._path_to_inode(dirname)
            self._remove_dirent(parent_inode, basename)
            
            # Decrement link count and delete inode if no more links
            inode.nlink -= 1
            if inode.nlink <= 0:
                self._free_blocks(inode.blocks)
                del self.inodes[inode_num]
            
            # Update metadata
            self._write_metadata()
            return True
            
        except Exception as e:
            print(f"Error deleting {path}: {e}")
            return False
    
    def list_directory(self, path: str = '/') -> List[str]:
        """
        List contents of a directory.
        
        Args:
            path: Path to the directory
            
        Returns:
            List of entry names in the directory
        """
        inode = self._path_to_inode(path)
        if not inode or inode.file_type != FileType.DIRECTORY:
            raise NotADirectoryError(f"Not a directory: {path}")
        
        # Update access time
        inode.atime = time.time()
        self._write_metadata()
        
        # Read directory entries
        entries = self._read_dir_entries(inode)
        
        # Filter out . and ..
        return [entry.name for entry in entries if entry.name not in ('.', '..')]
    
    def _path_to_inode(self, path: str) -> Inode:
        """Convert a path to an inode."""
        if not path or path == '/':
            return self.inodes[1]  # Root directory
        
        components = [c for c in path.split('/') if c]
        current_inode = self.inodes[1]  # Start at root
        
        for component in components:
            if current_inode.file_type != FileType.DIRECTORY:
                raise NotADirectoryError(f"Not a directory: {component}")
            
            # Find the directory entry
            found = False
            for entry in self._read_dir_entries(current_inode):
                if entry.name == component:
                    current_inode = self.inodes[entry.inode_num]
                    found = True
                    break
            
            if not found:
                raise FileNotFoundError(f"No such file or directory: {component}")
        
        return current_inode
    
    def _get_inode_number(self, inode: Inode) -> int:
        """Get the inode number for a given inode."""
        for num, i in self.inodes.items():
            if i is inode:
                return num
        raise ValueError("Inode not found")
    
    def _lookup(self, dir_inode: Inode, name: str) -> int:
        """Look up a name in a directory."""
        if dir_inode.file_type != FileType.DIRECTORY:
            raise NotADirectoryError("Not a directory")
        
        for entry in self._read_dir_entries(dir_inode):
            if entry.name == name:
                return entry.inode_num
        
        raise FileNotFoundError(f"No such file or directory: {name}")
    
    def _read_dir_entries(self, dir_inode: Inode) -> List[DirectoryEntry]:
        """Read all directory entries."""
        if dir_inode.file_type != FileType.DIRECTORY:
            raise NotADirectoryError("Not a directory")
        
        entries = []
        data = self._read_data(dir_inode)
        
        pos = 0
        while pos < len(data):
            # Read entry length
            if pos + 4 > len(data):
                break
            
            name_len = struct.unpack('!I', data[pos:pos+4])[0]
            pos += 4
            
            # Check if we have enough data
            if pos + name_len + 8 > len(data):
                break
            
            # Read name and inode number
            name = data[pos:pos+name_len].decode('utf-8')
            pos += name_len
            
            inode_num = struct.unpack('!Q', data[pos:pos+8])[0]
            pos += 8
            
            entries.append(DirectoryEntry(name, inode_num))
        
        return entries
    
    def _add_dirent(self, dir_inode: Inode, name: str, inode_num: int) -> None:
        """Add a directory entry."""
        if dir_inode.file_type != FileType.DIRECTORY:
            raise NotADirectoryError("Not a directory")
        
        # Create new directory entry
        entry = DirectoryEntry(name, inode_num)
        entry_data = entry.to_bytes()
        
        # Read existing entries
        entries = self._read_dir_entries(dir_inode)
        
        # Check if entry already exists
        for e in entries:
            if e.name == name:
                raise FileExistsError(f"File exists: {name}")
        
        # Add new entry
        entries.append(entry)
        
        # Serialize all entries
        entries_data = []
        for e in entries:
            entries_data.append(e.to_bytes())
        
        # Write back to disk
        self._write_data(dir_inode, b''.join(entries_data))
        
        # Update directory size and mtime
        dir_inode.size = len(b''.join(entries_data))
        dir_inode.mtime = time.time()
    
    def _remove_dirent(self, dir_inode: Inode, name: str) -> None:
        """Remove a directory entry."""
        if dir_inode.file_type != FileType.DIRECTORY:
            raise NotADirectoryError("Not a directory")
        
        # Read existing entries
        entries = self._read_dir_entries(dir_inode)
        
        # Find and remove the entry
        new_entries = []
        found = False
        for e in entries:
            if e.name == name:
                found = True
            else:
                new_entries.append(e)
        
        if not found:
            raise FileNotFoundError(f"No such file or directory: {name}")
        
        # Serialize remaining entries
        entries_data = [e.to_bytes() for e in new_entries]
        
        # Write back to disk
        self._write_data(dir_inode, b''.join(entries_data))
        
        # Update directory size and mtime
        dir_inode.size = len(b''.join(entries_data))
        dir_inode.mtime = time.time()
    
    def _read_data(self, inode: Inode) -> bytes:
        """Read data from a file."""
        if not inode.blocks:
            return b''
        
        data = bytearray()
        with open(self.disk_path, 'rb') as f:
            for block_num in inode.blocks:
                f.seek(block_num * BLOCK_SIZE)
                data.extend(f.read(BLOCK_SIZE))
        
        return bytes(data[:inode.size])
    
    def _write_data(self, inode: Inode, data: bytes) -> int:
        """Write data to a file."""
        # Calculate number of blocks needed
        data_len = len(data)
        blocks_needed = (data_len + BLOCK_SIZE - 1) // BLOCK_SIZE
        
        # Free existing blocks if needed
        if inode.blocks:
            self._free_blocks(inode.blocks)
            inode.blocks = []
        
        # Allocate new blocks
        if blocks_needed > 0:
            inode.blocks = self._allocate_blocks(blocks_needed)
        
        # Write data to blocks
        with open(self.disk_path, 'r+b') as f:
            for i, block_num in enumerate(inode.blocks):
                offset = i * BLOCK_SIZE
                chunk = data[offset:offset + BLOCK_SIZE]
                
                # Pad last block if needed
                if len(chunk) < BLOCK_SIZE:
                    chunk = chunk.ljust(BLOCK_SIZE, b'\0')
                
                f.seek(block_num * BLOCK_SIZE)
                f.write(chunk)
        
        # Update inode
        inode.size = data_len
        inode.mtime = time.time()
        inode.atime = time.time()
        
        return data_len
    
    def _allocate_blocks(self, count: int) -> List[int]:
        """Allocate new blocks from the free list."""
        if len(self.free_blocks) < count:
            raise IOError("Not enough free space on disk")
        
        allocated = sorted(self.free_blocks)[:count]
        self.free_blocks -= set(allocated)
        self.used_blocks.update(allocated)
        
        # Update metadata
        self._write_metadata()
        
        return allocated
    
    def _free_blocks(self, blocks: List[int]) -> None:
        """Mark blocks as free."""
        blocks = set(blocks)
        self.used_blocks -= blocks
        self.free_blocks.update(blocks)
        
        # Update metadata
        self._write_metadata()

# Example usage
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python -m virtual_disk.disk <command> [args...]")
        print("Commands:")
        print("  create <disk_path> <size_mb> - Create a new virtual disk")
        print("  ls <disk_path> [path] - List directory contents")
        print("  mkdir <disk_path> <path> - Create a directory")
        print("  write <disk_path> <file_path> <content> - Write to a file")
        print("  read <disk_path> <file_path> - Read a file")
        print("  rm <disk_path> <path> - Remove a file or directory")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "create":
        if len(sys.argv) != 4:
            print("Usage: python -m virtual_disk.disk create <disk_path> <size_mb>")
            sys.exit(1)
        
        disk_path = sys.argv[2]
        size_mb = int(sys.argv[3])
        
        try:
            disk = VirtualDisk(disk_path, size_mb, create=True)
            print(f"Created virtual disk at {disk_path} ({size_mb}MB)")
        except Exception as e:
            print(f"Error creating disk: {e}")
            sys.exit(1)
    
    elif command in ("ls", "mkdir", "write", "read", "rm"):
        if len(sys.argv) < 3:
            print(f"Usage: python -m virtual_disk.disk {command} <disk_path> [args...]")
            sys.exit(1)
        
        disk_path = sys.argv[2]
        
        try:
            disk = VirtualDisk(disk_path)
            
            if command == "ls":
                path = sys.argv[3] if len(sys.argv) > 3 else "/"
                try:
                    entries = disk.list_directory(path)
                    for entry in entries:
                        print(entry)
                except Exception as e:
                    print(f"Error listing directory: {e}")
                    sys.exit(1)
            
            elif command == "mkdir":
                if len(sys.argv) != 4:
                    print("Usage: python -m virtual_disk.disk mkdir <disk_path> <path>")
                    sys.exit(1)
                
                path = sys.argv[3]
                try:
                    disk.create_file(path, file_type=FileType.DIRECTORY)
                    print(f"Created directory: {path}")
                except Exception as e:
                    print(f"Error creating directory: {e}")
                    sys.exit(1)
            
            elif command == "write":
                if len(sys.argv) != 5:
                    print("Usage: python -m virtual_disk.disk write <disk_path> <file_path> <content>")
                    sys.exit(1)
                
                path = sys.argv[3]
                content = sys.argv[4].encode('utf-8')
                
                try:
                    bytes_written = disk.write_file(path, content)
                    print(f"Wrote {bytes_written} bytes to {path}")
                except Exception as e:
                    print(f"Error writing file: {e}")
                    sys.exit(1)
            
            elif command == "read":
                if len(sys.argv) != 4:
                    print("Usage: python -m virtual_disk.disk read <disk_path> <file_path>")
                    sys.exit(1)
                
                path = sys.argv[3]
                
                try:
                    content = disk.read_file(path)
                    print(content.decode('utf-8', 'replace'))
                except Exception as e:
                    print(f"Error reading file: {e}")
                    sys.exit(1)
            
            elif command == "rm":
                if len(sys.argv) != 4:
                    print("Usage: python -m virtual_disk.disk rm <disk_path> <path>")
                    sys.exit(1)
                
                path = sys.argv[3]
                
                try:
                    if disk.delete_file(path, recursive=True):
                        print(f"Removed: {path}")
                    else:
                        print(f"Failed to remove: {path}")
                        sys.exit(1)
                except Exception as e:
                    print(f"Error removing: {e}")
                    sys.exit(1)
        
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)
    
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)
