#!/usr/bin/env python3

print("Hello from CloudSim!")
print("Testing basic functionality...")

# Test imports
try:
    from storage_virtual_node import StorageVirtualNode
    from storage_virtual_network import StorageVirtualNetwork
    print("✓ Imports successful")
except ImportError as e:
    print(f"✗ Import failed: {e}")
    exit(1)

# Test basic node creation
try:
    node = StorageVirtualNode("test_node", 4, 8, 100, 100)
    print("✓ Node creation successful")
    print(f"  Node ID: {node.node_id}")
    print(f"  Storage: {node.total_storage / (1024**3):.1f} GB")
    print(f"  Bandwidth: {node.bandwidth / 1000000:.0f} Mbps")
except Exception as e:
    print(f"✗ Node creation failed: {e}")

# Test network creation
try:
    network = StorageVirtualNetwork()
    network.add_node(node)
    print("✓ Network creation successful")
    print(f"  Nodes in network: {len(network.nodes)}")
except Exception as e:
    print(f"✗ Network creation failed: {e}")

print("\nBasic test completed!")


