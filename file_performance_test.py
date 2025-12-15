#!/usr/bin/env python3
"""
File-based Performance Test for CloudSim
Results are written to a file for analysis.
"""

import time
import json
import os
from storage_virtual_node import StorageVirtualNode
from storage_virtual_network import StorageVirtualNetwork


def log_message(message, log_file="performance_log.txt"):
    """Log a message to file and print it"""
    with open(log_file, "a", encoding="utf-8") as f:
        timestamp = time.strftime("%H:%M:%S")
        f.write(f"[{timestamp}] {message}\n")
    print(message)


def run_performance_tests():
    """Run comprehensive performance tests and save results to file"""

    log_file = "performance_results.txt"
    results_file = "performance_data.json"

    # Clear previous log
    if os.path.exists(log_file):
        os.remove(log_file)

    log_message("🚀 CLOUDSIM PERFORMANCE TEST STARTED")
    log_message("=" * 60)

    results = {
        "test_timestamp": time.time(),
        "tests": {}
    }

    # Setup test network
    log_message("\n📡 Setting up test network...")
    network = StorageVirtualNetwork()

    # Create nodes with different capacities
    nodes_config = [
        ("node_0", 4, 8, 200, 200),   # High capacity node
        ("node_1", 2, 4, 100, 100),   # Medium capacity node
        ("node_2", 8, 16, 500, 500),  # Very high capacity node
        ("node_3", 1, 2, 50, 50),     # Low capacity node
    ]

    for node_id, cpu, mem, storage, bandwidth in nodes_config:
        node = StorageVirtualNode(node_id, cpu, mem, storage, bandwidth)
        network.add_node(node)
        log_message(f"  ✓ Created {node_id}: {storage}GB storage, {bandwidth}Mbps bandwidth")

    # Connect nodes in mesh topology
    connections = []
    for i in range(len(nodes_config)):
        for j in range(i + 1, len(nodes_config)):
            bw = min(200, 100 + abs(i - j) * 30)  # Varying bandwidth
            network.connect_nodes(nodes_config[i][0], nodes_config[j][0], bw)
            connections.append((nodes_config[i][0], nodes_config[j][0], bw))

    log_message(f"  ✓ Created {len(connections)} network connections")

    # Test 1: File Transfer Performance
    log_message("\n📁 FILE TRANSFER PERFORMANCE TEST")
    log_message("-" * 40)

    file_sizes_mb = [1, 5, 25, 100]
    transfer_results = {}

    for size_mb in file_sizes_mb:
        log_message(f"\nTesting {size_mb}MB file transfers...")
        transfer_times = []
        throughputs = []

        for i in range(3):  # 3 transfers per size
            source = nodes_config[i % len(nodes_config)][0]
            target = nodes_config[(i + 1) % len(nodes_config)][0]

            start_time = time.time()

            transfer = network.initiate_file_transfer(
                source, target, f"perf_test_{size_mb}mb_{i}.dat", size_mb * 1024 * 1024
            )

            if transfer:
                file_id = transfer.file_id
                total_chunks = len(transfer.chunks)
                chunks_processed = 0

                while chunks_processed < total_chunks:
                    chunks_this_step, complete = network.process_file_transfer(
                        source, target, file_id, chunks_per_step=10
                    )
                    chunks_processed += chunks_this_step

                    if not complete and chunks_this_step == 0:
                        break

                if transfer.status.name == 'COMPLETED':
                    end_time = time.time()
                    transfer_time = end_time - start_time
                    throughput = size_mb / transfer_time  # MB/s

                    transfer_times.append(transfer_time)
                    throughputs.append(throughput)

                    log_message(".2f"
                else:
                    log_message(f"  Transfer {i+1} failed")
            else:
                log_message(f"  Transfer {i+1} initiation failed")

        if transfer_times:
            avg_time = sum(transfer_times) / len(transfer_times)
            avg_throughput = sum(throughputs) / len(throughputs)
            min_throughput = min(throughputs)
            max_throughput = max(throughputs)

            transfer_results[size_mb] = {
                "avg_transfer_time_sec": avg_time,
                "avg_throughput_mbps": avg_throughput,
                "min_throughput_mbps": min_throughput,
                "max_throughput_mbps": max_throughput,
                "successful_transfers": len(transfer_times),
                "total_transfers": 3
            }

            log_message(f"  📊 {size_mb}MB Results: {avg_throughput:.2f} MB/s avg, "
                       f"{len(transfer_times)}/3 successful")

    results["tests"]["file_transfer"] = transfer_results

    # Test 2: Concurrent Transfers
    log_message("\n🔄 CONCURRENT TRANSFER TEST")
    log_message("-" * 40)

    num_concurrent = 6
    concurrent_file_size = 10  # MB

    log_message(f"Testing {num_concurrent} concurrent {concurrent_file_size}MB transfers...")

    start_time = time.time()
    successful_concurrent = 0
    concurrent_times = []
    concurrent_throughputs = []

    for i in range(num_concurrent):
        source = nodes_config[i % len(nodes_config)][0]
        target = nodes_config[(i + 1) % len(nodes_config)][0]

        transfer_start = time.time()
        transfer = network.initiate_file_transfer(
            source, target, f"concurrent_{i}.dat", concurrent_file_size * 1024 * 1024
        )

        if transfer:
            file_id = transfer.file_id
            total_chunks = len(transfer.chunks)
            chunks_processed = 0

            while chunks_processed < total_chunks:
                chunks_this_step, complete = network.process_file_transfer(
                    source, target, file_id, chunks_per_step=5
                )
                chunks_processed += chunks_this_step

                if not complete and chunks_this_step == 0:
                    break

            if transfer.status.name == 'COMPLETED':
                transfer_end = time.time()
                transfer_time = transfer_end - transfer_start
                throughput = concurrent_file_size / transfer_time

                concurrent_times.append(transfer_time)
                concurrent_throughputs.append(throughput)
                successful_concurrent += 1

    end_time = time.time()
    total_concurrent_time = end_time - start_time

    concurrent_results = {
        "num_concurrent_transfers": num_concurrent,
        "file_size_mb": concurrent_file_size,
        "total_time_sec": total_concurrent_time,
        "successful_transfers": successful_concurrent,
        "success_rate": successful_concurrent / num_concurrent
    }

    if concurrent_times:
        concurrent_results.update({
            "avg_transfer_time_sec": sum(concurrent_times) / len(concurrent_times),
            "avg_throughput_mbps": sum(concurrent_throughputs) / len(concurrent_throughputs),
            "total_throughput_mbps": sum(concurrent_throughputs)
        })

    results["tests"]["concurrent_transfers"] = concurrent_results

    log_message(f"  ✅ {successful_concurrent}/{num_concurrent} concurrent transfers completed")
    log_message(".2f"    if concurrent_throughputs:
        log_message(f"  📊 Total throughput: {sum(concurrent_throughputs):.2f} MB/s")
        log_message(f"  📊 Average per transfer: {sum(concurrent_throughputs)/len(concurrent_throughputs):.2f} MB/s")

    # Test 3: Network Utilization
    log_message("\n🌐 NETWORK UTILIZATION TEST")
    log_message("-" * 40)

    log_message("Monitoring network stats during load...")

    # Generate some load
    load_transfers = []
    for i in range(8):
        source = nodes_config[i % len(nodes_config)][0]
        target = nodes_config[(i + 2) % len(nodes_config)][0]

        transfer = network.initiate_file_transfer(
            source, target, f"load_test_{i}.dat", 20 * 1024 * 1024  # 20MB
        )
        if transfer:
            load_transfers.append((source, target, transfer.file_id))

    # Process some chunks to generate utilization
    for source, target, file_id in load_transfers[:4]:  # Process first 4 transfers
        network.process_file_transfer(source, target, file_id, chunks_per_step=20)

    # Get network stats
    network_stats = network.get_network_stats()
    utilization_results = {
        "network_stats": network_stats,
        "active_transfers": len(load_transfers)
    }

    results["tests"]["network_utilization"] = utilization_results

    log_message(f"  📊 Total bandwidth: {network_stats['total_bandwidth_bps'] / 1000000:.0f} Mbps")
    log_message(f"  📊 Used bandwidth: {network_stats['used_bandwidth_bps'] / 1000000:.1f} Mbps")
    log_message(f"  📊 Bandwidth utilization: {network_stats['bandwidth_utilization']:.1f}%")
    log_message(f"  📊 Total storage: {network_stats['total_storage_bytes'] / (1024**3):.1f} GB")
    log_message(f"  📊 Storage utilization: {network_stats['storage_utilization']:.1f}%")
    log_message(f"  📊 Active transfers: {network_stats['active_transfers']}")

    # Save results
    with open(results_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    log_message("
💾 Results saved to performance_data.json"    log_message(f"📝 Detailed log saved to {log_file}")

    # Summary
    log_message("\n" + "=" * 60)
    log_message("🎯 PERFORMANCE TEST SUMMARY")
    log_message("=" * 60)

    if transfer_results:
        log_message("\n📁 FILE TRANSFER PERFORMANCE:")
        for size, data in transfer_results.items():
            log_message(f"  {size}MB: {data['avg_throughput_mbps']:.2f} MB/s avg "
                       f"({data['successful_transfers']}/{data['total_transfers']} successful)")

    if concurrent_results.get('avg_throughput_mbps'):
        log_message("\n🔄 CONCURRENT PERFORMANCE:")
        log_message(f"  Success rate: {concurrent_results['success_rate']:.1%}")
        log_message(f"  Total throughput: {concurrent_results['total_throughput_mbps']:.2f} MB/s")

    log_message("\n✅ PERFORMANCE TESTS COMPLETED!")
    log_message("=" * 60)

    return results


if __name__ == "__main__":
    run_performance_tests()

