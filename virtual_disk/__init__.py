"""
Virtual Disk Module for Cloud Storage System

This module provides a virtual disk implementation with a simple file system
that can be used for storing files and directories in a block-based format.
"""

from .disk import VirtualDisk, FileType, Permission

__all__ = ['VirtualDisk', 'FileType', 'Permission']
