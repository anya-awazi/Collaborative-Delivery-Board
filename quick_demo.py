#!/usr/bin/env python3
"""
Quick Demo of CloudSim Performance Testing

Run this to see immediate performance results for your CloudSim system.
"""

import time
from storage_virtual_node import StorageVirtualNode
from storage_virtual_network import StorageVirtualNetwork


def demo_file_transfer():
    """Demonstrate file transfer performance"""
    print("🚀 CLOUDSIM FILE TRANSFER DEMO")
    print("=" * 40)

    # Create a simple network
    network = StorageVirtualNetwork()

    # Add two nodes
    node1 = StorageVirtualNode("server_1", 4, 8, 500, 200)  # 4CPU, 8GB, 500GB, 200Mbps
    node2 = StorageVirtualNode("server_2", 4, 8, 500, 200)  # Same specs

    network.add_node(node1)
    network.add_node(node2)
    network.connect_nodes("server_1", "server_2", 200)

    print("✓ Created network with 2 storage nodes")

    # Test different file sizes
    file_sizes = [10, 50, 100]  # MB

    for size_mb in file_sizes:
        print(f"\n📁 Testing {size_mb}MB file transfer...")

        start_time = time.time()

        # Initiate transfer
        transfer = network.initiate_file_transfer(
            "server_1", "server_2",
            f"demo_file_{size_mb}mb.dat",
            size_mb * 1024 * 1024
        )

        if not transfer:
            print(f"  ❌ Transfer initiation failed (insufficient storage?)")
            continue

        file_id = transfer.file_id
        total_chunks = len(transfer.chunks)
        chunks_processed = 0

        print(f"  Transferring {total_chunks} chunks...")

        # Process transfer
        while chunks_processed < total_chunks:
            chunks_this_step, complete = network.process_file_transfer(
                "server_1", "server_2", file_id, chunks_per_step=10
            )
            chunks_processed += chunks_this_step

            # Show progress
            progress = (chunks_processed / total_chunks) * 100
            print(".1f"
            if not complete and chunks_this_step == 0:
                break

        end_time = time.time()
        transfer_time = end_time - start_time

        if transfer.status.name == 'COMPLETED':
            throughput = size_mb / transfer_time  # MB/s
            print(".2f"            print(".2f"        else:
            print("  ❌ Transfer failed to complete"
    # Show network stats
    print("
🌐 Final Network Statistics:"    stats = network.get_network_stats()
    print(f"  Total bandwidth: {stats['total_bandwidth_bps'] / 1000000:.0f} Mbps")
    print(f"  Used bandwidth: {stats['used_bandwidth_bps'] / 1000000:.1f} Mbps")
    print(f"  Bandwidth utilization: {stats['bandwidth_utilization']:.1f}%")
    print(f"  Total storage: {stats['total_storage_bytes'] / (1024**3):.1f} GB")
    print(f"  Used storage: {stats['used_storage_bytes'] / (1024**3):.1f} GB")
    print(f"  Storage utilization: {stats['storage_utilization']:.1f}%")


def demo_concurrent_transfers():
    """Demonstrate concurrent transfer performance"""
    print("\n🔄 CONCURRENT TRANSFER DEMO")
    print("=" * 40)

    # Create network with 4 nodes
    network = StorageVirtualNetwork()

    nodes = []
    for i in range(4):
        node = StorageVirtualNode(f"node_{i}", 2, 4, 200, 100)
        network.add_node(node)
        nodes.append(f"node_{i}")

    # Connect all nodes
    for i in range(4):
        for j in range(i + 1, 4):
            network.connect_nodes(nodes[i], nodes[j], 100)

    print("✓ Created network with 4 nodes in mesh topology")

    # Start 4 concurrent transfers
    num_transfers = 4
    file_size_mb = 25

    print(f"\nStarting {num_transfers} concurrent {file_size_mb}MB transfers...")

    transfers = []
    for i in range(num_transfers):
        source = nodes[i % 4]
        target = nodes[(i + 1) % 4]

        transfer = network.initiate_file_transfer(
            source, target,
            f"concurrent_demo_{i}.dat",
            file_size_mb * 1024 * 1024
        )

        if transfer:
            transfers.append({
                'id': i,
                'source': source,
                'target': target,
                'file_id': transfer.file_id,
                'total_chunks': len(transfer.chunks),
                'completed': False
            })

    print(f"✓ Initiated {len(transfers)} transfers")

    # Process transfers concurrently (simplified)
    start_time = time.time()
    active_transfers = len(transfers)
    total_chunks_processed = 0

    while active_transfers > 0 and total_chunks_processed < 500:  # Safety limit
        for transfer_info in transfers:
            if not transfer_info['completed']:
                chunks_step, complete = network.process_file_transfer(
                    transfer_info['source'],
                    transfer_info['target'],
                    transfer_info['file_id'],
                    chunks_per_step=5
                )

                if complete:
                    transfer_info['completed'] = True
                    active_transfers -= 1

        total_chunks_processed += 1

        # Progress update
        if total_chunks_processed % 50 == 0:
            completed = sum(1 for t in transfers if t['completed'])
            print(f"  Progress: {completed}/{len(transfers)} transfers completed")

    end_time = time.time()
    total_time = end_time - start_time

    successful = sum(1 for t in transfers if t['completed'])
    success_rate = successful / len(transfers)

    print("
📊 Concurrent Transfer Results:"    print(f"  Total time: {total_time:.2f} seconds")
    print(f"  Success rate: {success_rate:.1%} ({successful}/{len(transfers)})")
    print(".2f"
    # Network stats after concurrent load
    stats = network.get_network_stats()
    print("
🌐 Network Status After Load:"    print(f"  Bandwidth utilization: {stats['bandwidth_utilization']:.1f}%")
    print(f"  Storage utilization: {stats['storage_utilization']:.1f}%")
    print(f"  Active transfers: {stats['active_transfers']}")


if __name__ == "__main__":
    print("CloudSim Performance Testing Demo")
    print("==================================")

    try:
        demo_file_transfer()
        demo_concurrent_transfers()

        print("\n" + "=" * 50)
        print("✅ DEMO COMPLETED!")
        print("=" * 50)
        print("\n💡 To run the full benchmark suite:")
        print("   python performance_benchmark.py")
        print("\n📁 Results will be saved to benchmark_results_[timestamp].json")

    except Exception as e:
        print(f"\n❌ Demo failed with error: {e}")
        print("Check that storage_virtual_node.py and storage_virtual_network.py are in the same directory.")


