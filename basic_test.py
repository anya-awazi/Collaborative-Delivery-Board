#!/usr/bin/env python3

# Write immediately to test if script runs
with open("test_started.txt", "w") as f:
    f.write("Script started at: " + str(__import__("time").time()) + "\n")

print("Basic test starting...")

try:
    import sys
    with open("test_started.txt", "a") as f:
        f.write("Python version: " + sys.version + "\n")
except Exception as e:
    with open("test_started.txt", "a") as f:
        f.write("Error getting version: " + str(e) + "\n")

try:
    from storage_virtual_node import StorageVirtualNode
    with open("test_started.txt", "a") as f:
        f.write("Import successful\n")
except ImportError as e:
    with open("test_started.txt", "a") as f:
        f.write("Import failed: " + str(e) + "\n")
    exit(1)

with open("test_started.txt", "a") as f:
    f.write("Basic test completed\n")

print("Basic test completed.")


