#!/usr/bin/env python3
"""
CloudSim Performance Benchmark Suite

This script provides comprehensive performance testing for the CloudSim
storage virtual network system. It measures:
- File transfer throughput and latency
- Network utilization under load
- Concurrent transfer performance
- Memory and CPU usage patterns

Usage:
    python performance_benchmark.py

Or for specific tests:
    python performance_benchmark.py --test file_transfer
    python performance_benchmark.py --test concurrent
    python performance_benchmark.py --test network
"""

import time
import json
import argparse
import sys
from typing import Dict, List
from storage_virtual_node import StorageVirtualNode
from storage_virtual_network import StorageVirtualNetwork


class CloudSimBenchmark:
    """Performance benchmark suite for CloudSim"""

    def __init__(self):
        self.network = None
        self.results = {}

    def create_test_network(self, num_nodes: int = 4) -> StorageVirtualNetwork:
        """Create a test network with specified number of nodes"""
        network = StorageVirtualNetwork()

        # Create nodes with realistic configurations
        node_configs = [
            ("web_server", 8, 16, 500, 1000),    # High-performance web server
            ("storage_node_1", 4, 32, 2000, 500),  # Large storage node
            ("storage_node_2", 4, 32, 2000, 500),  # Large storage node
            ("edge_node", 2, 8, 100, 200),        # Edge computing node
            ("backup_node", 4, 16, 1000, 300),    # Backup storage node
            ("compute_node", 16, 64, 500, 200),   # High-compute node
        ][:num_nodes]  # Limit to requested number

        for node_id, cpu, mem, storage, bandwidth in node_configs:
            node = StorageVirtualNode(node_id, cpu, mem, storage, bandwidth)
            network.add_node(node)

        # Create mesh network topology
        node_ids = list(network.nodes.keys())
        for i in range(len(node_ids)):
            for j in range(i + 1, len(node_ids)):
                # Bandwidth based on node capabilities and distance
                base_bw = min(network.nodes[node_ids[i]].bandwidth,
                            network.nodes[node_ids[j]].bandwidth) // 1000000
                distance_factor = abs(i - j)
                connection_bw = max(50, base_bw - distance_factor * 20)
                network.connect_nodes(node_ids[i], node_ids[j], connection_bw)

        self.network = network
        return network

    def benchmark_file_transfers(self, file_sizes_mb: List[int] = [10, 50, 100, 500]) -> Dict:
        """Benchmark file transfer performance"""
        print("\n📁 FILE TRANSFER BENCHMARK")
        print("=" * 50)

        results = {
            'file_sizes_tested': file_sizes_mb,
            'transfers_per_size': 3,
            'performance_data': {}
        }

        for size_mb in file_sizes_mb:
            print(f"\nTesting {size_mb}MB file transfers...")
            transfer_metrics = []

            for i in range(3):  # 3 transfers per size for statistical significance
                # Select different source/target combinations
                node_ids = list(self.network.nodes.keys())
                source_id = node_ids[i % len(node_ids)]
                target_id = node_ids[(i + 1) % len(node_ids)]

                start_time = time.time()

                # Initiate transfer
                transfer = self.network.initiate_file_transfer(
                    source_id, target_id,
                    f"benchmark_{size_mb}mb_{i}.dat",
                    size_mb * 1024 * 1024
                )

                if not transfer:
                    print(f"  ❌ Transfer {i+1} failed to initiate")
                    continue

                file_id = transfer.file_id
                total_chunks = len(transfer.chunks)
                chunks_processed = 0
                transfer_start = time.time()

                # Process transfer
                while chunks_processed < total_chunks:
                    chunks_step, complete = self.network.process_file_transfer(
                        source_id, target_id, file_id, chunks_per_step=20
                    )
                    chunks_processed += chunks_step

                    if not complete and chunks_step == 0:
                        break

                transfer_end = time.time()

                if transfer.status.name == 'COMPLETED':
                    total_time = transfer_end - transfer_start
                    throughput = size_mb / total_time  # MB/s

                    transfer_metrics.append({
                        'transfer_time': total_time,
                        'throughput_mbps': throughput,
                        'chunks_total': total_chunks,
                        'success': True
                    })

                    print(".1f"                          f"({chunks_processed}/{total_chunks} chunks)")
                else:
                    transfer_metrics.append({
                        'transfer_time': transfer_end - transfer_start,
                        'throughput_mbps': 0,
                        'chunks_total': total_chunks,
                        'success': False
                    })
                    print(f"  ❌ Transfer {i+1} failed to complete")

            # Calculate statistics
            if transfer_metrics:
                successful_transfers = [m for m in transfer_metrics if m['success']]
                if successful_transfers:
                    avg_throughput = sum(m['throughput_mbps'] for m in successful_transfers) / len(successful_transfers)
                    avg_time = sum(m['transfer_time'] for m in successful_transfers) / len(successful_transfers)
                    success_rate = len(successful_transfers) / len(transfer_metrics)

                    results['performance_data'][size_mb] = {
                        'average_throughput_mbps': avg_throughput,
                        'average_transfer_time_sec': avg_time,
                        'success_rate': success_rate,
                        'successful_transfers': len(successful_transfers),
                        'total_transfers': len(transfer_metrics)
                    }

                    print(f"  📊 {size_mb}MB Summary: {avg_throughput:.2f} MB/s avg, "
                          f"{success_rate:.1%} success rate")

        return results

    def benchmark_concurrent_transfers(self, num_concurrent: int = 10,
                                     file_size_mb: int = 25) -> Dict:
        """Benchmark concurrent transfer performance"""
        print(f"\n🔄 CONCURRENT TRANSFER BENCHMARK")
        print("=" * 50)
        print(f"Testing {num_concurrent} concurrent {file_size_mb}MB transfers...")

        results = {
            'num_concurrent_transfers': num_concurrent,
            'file_size_mb': file_size_mb,
            'transfer_results': [],
            'summary': {}
        }

        start_time = time.time()
        transfer_threads = []

        # Initiate all transfers
        for i in range(num_concurrent):
            node_ids = list(self.network.nodes.keys())
            source_id = node_ids[i % len(node_ids)]
            target_id = node_ids[(i + 1) % len(node_ids)]

            transfer = self.network.initiate_file_transfer(
                source_id, target_id,
                f"concurrent_{i}.dat",
                file_size_mb * 1024 * 1024
            )

            if transfer:
                transfer_threads.append({
                    'id': i,
                    'source': source_id,
                    'target': target_id,
                    'file_id': transfer.file_id,
                    'total_chunks': len(transfer.chunks),
                    'start_time': None,
                    'end_time': None,
                    'completed': False
                })

        # Process transfers (simplified concurrent processing)
        active_transfers = len(transfer_threads)
        total_chunks_processed = 0

        while active_transfers > 0 and total_chunks_processed < 1000:  # Safety limit
            for transfer_info in transfer_threads:
                if not transfer_info['completed']:
                    if transfer_info['start_time'] is None:
                        transfer_info['start_time'] = time.time()

                    chunks_step, complete = self.network.process_file_transfer(
                        transfer_info['source'],
                        transfer_info['target'],
                        transfer_info['file_id'],
                        chunks_per_step=5
                    )

                    if complete or chunks_step == 0:
                        transfer_info['end_time'] = time.time()
                        transfer_info['completed'] = complete
                        active_transfers -= 1

                        if complete:
                            transfer_time = transfer_info['end_time'] - transfer_info['start_time']
                            throughput = file_size_mb / transfer_time
                            results['transfer_results'].append({
                                'transfer_id': transfer_info['id'],
                                'transfer_time_sec': transfer_time,
                                'throughput_mbps': throughput,
                                'success': True
                            })
                        else:
                            results['transfer_results'].append({
                                'transfer_id': transfer_info['id'],
                                'transfer_time_sec': 0,
                                'throughput_mbps': 0,
                                'success': False
                            })

            total_chunks_processed += 1

        end_time = time.time()
        total_duration = end_time - start_time

        # Calculate summary statistics
        successful_results = [r for r in results['transfer_results'] if r['success']]
        success_rate = len(successful_results) / num_concurrent if results['transfer_results'] else 0

        results['summary'] = {
            'total_duration_sec': total_duration,
            'success_rate': success_rate,
            'successful_transfers': len(successful_results),
            'total_transfers': len(results['transfer_results'])
        }

        if successful_results:
            avg_throughput = sum(r['throughput_mbps'] for r in successful_results) / len(successful_results)
            total_throughput = sum(r['throughput_mbps'] for r in successful_results)
            avg_transfer_time = sum(r['transfer_time_sec'] for r in successful_results) / len(successful_results)

            results['summary'].update({
                'average_throughput_per_transfer_mbps': avg_throughput,
                'total_network_throughput_mbps': total_throughput,
                'average_transfer_time_sec': avg_transfer_time
            })

        print(f"  ⏱️  Total duration: {total_duration:.2f} seconds")
        print(f"  ✅ Success rate: {success_rate:.1%}")
        if successful_results:
            print(f"  📊 Average throughput per transfer: {avg_throughput:.2f} MB/s")
            print(f"  📊 Total network throughput: {total_throughput:.2f} MB/s")

        return results

    def benchmark_network_utilization(self, duration_sec: int = 30) -> Dict:
        """Benchmark network utilization over time"""
        print(f"\n🌐 NETWORK UTILIZATION BENCHMARK")
        print("=" * 50)
        print(f"Monitoring network for {duration_sec} seconds under load...")

        results = {
            'duration_sec': duration_sec,
            'measurements': [],
            'summary': {}
        }

        # Start background load generation
        load_transfers = []
        for i in range(8):
            node_ids = list(self.network.nodes.keys())
            source_id = node_ids[i % len(node_ids)]
            target_id = node_ids[(i + 2) % len(node_ids)]

            transfer = self.network.initiate_file_transfer(
                source_id, target_id,
                f"load_test_{i}.dat",
                50 * 1024 * 1024  # 50MB files
            )
            if transfer:
                load_transfers.append({
                    'source': source_id,
                    'target': target_id,
                    'file_id': transfer.file_id
                })

        print(f"  📡 Generated {len(load_transfers)} background transfers")

        # Monitor utilization
        start_time = time.time()
        measurements = []

        while time.time() - start_time < duration_sec:
            # Process some transfer chunks to generate load
            for transfer_info in load_transfers:
                self.network.process_file_transfer(
                    transfer_info['source'],
                    transfer_info['target'],
                    transfer_info['file_id'],
                    chunks_per_step=10
                )

            # Take measurement
            stats = self.network.get_network_stats()
            measurement = {
                'timestamp': time.time() - start_time,
                'network_stats': stats
            }
            measurements.append(measurement)

            time.sleep(2)  # Sample every 2 seconds

        results['measurements'] = measurements

        # Calculate summary statistics
        if measurements:
            bandwidth_utils = [m['network_stats']['bandwidth_utilization'] for m in measurements]
            storage_utils = [m['network_stats']['storage_utilization'] for m in measurements]

            results['summary'] = {
                'avg_bandwidth_utilization': sum(bandwidth_utils) / len(bandwidth_utils),
                'max_bandwidth_utilization': max(bandwidth_utils),
                'min_bandwidth_utilization': min(bandwidth_utils),
                'avg_storage_utilization': sum(storage_utils) / len(storage_utils),
                'max_storage_utilization': max(storage_utils),
                'final_active_transfers': measurements[-1]['network_stats']['active_transfers']
            }

            print(f"  📊 Bandwidth utilization: {results['summary']['avg_bandwidth_utilization']:.1f}% avg, "
                  f"{results['summary']['max_bandwidth_utilization']:.1f}% peak")
            print(f"  📊 Storage utilization: {results['summary']['avg_storage_utilization']:.1f}% avg, "
                  f"{results['summary']['max_storage_utilization']:.1f}% peak")

        return results

    def run_full_benchmark(self) -> Dict:
        """Run the complete benchmark suite"""
        print("🚀 CLOUDSIM PERFORMANCE BENCHMARK SUITE")
        print("=" * 60)
        print(f"Started at: {time.strftime('%Y-%m-%d %H:%M:%S')}")

        # Create test network
        print("\n🏗️  Setting up test network...")
        self.create_test_network(num_nodes=5)
        print(f"  ✓ Created network with {len(self.network.nodes)} nodes")

        # Run benchmarks
        self.results['file_transfer_benchmark'] = self.benchmark_file_transfers()
        self.results['concurrent_transfer_benchmark'] = self.benchmark_concurrent_transfers()
        self.results['network_utilization_benchmark'] = self.benchmark_network_utilization()

        # Save results
        results_file = f"benchmark_results_{int(time.time())}.json"
        with open(results_file, 'w') as f:
            json.dump(self.results, f, indent=2, default=str)

        print(f"\n💾 Results saved to: {results_file}")

        # Print summary
        self.print_benchmark_summary()

        return self.results

    def print_benchmark_summary(self):
        """Print a summary of benchmark results"""
        print("\n" + "=" * 60)
        print("📊 BENCHMARK SUMMARY REPORT")
        print("=" * 60)

        # File transfer summary
        if 'file_transfer_benchmark' in self.results:
            ft_data = self.results['file_transfer_benchmark']
            print("\n📁 FILE TRANSFER PERFORMANCE:")
            for size, data in ft_data['performance_data'].items():
                print(f"  {size}MB files: {data['average_throughput_mbps']:.2f} MB/s avg, "
                      f"{data['success_rate']:.1%} success rate")

        # Concurrent transfer summary
        if 'concurrent_transfer_benchmark' in self.results:
            ct_data = self.results['concurrent_transfer_benchmark']
            summary = ct_data['summary']
            print("\n🔄 CONCURRENT TRANSFER PERFORMANCE:")
            print(f"  {summary['successful_transfers']}/{summary['total_transfers']} transfers successful")
            print(f"  Success rate: {summary['success_rate']:.1%}")
            if 'average_throughput_per_transfer_mbps' in summary:
                print(f"  Per-transfer throughput: {summary['average_throughput_per_transfer_mbps']:.2f} MB/s")
                print(f"  Total network throughput: {summary['total_network_throughput_mbps']:.2f} MB/s")

        # Network utilization summary
        if 'network_utilization_benchmark' in self.results:
            nu_data = self.results['network_utilization_benchmark']
            summary = nu_data['summary']
            print("\n🌐 NETWORK UTILIZATION:")
            print(f"  Bandwidth: {summary['avg_bandwidth_utilization']:.1f}% avg, "
                  f"{summary['max_bandwidth_utilization']:.1f}% peak")
            print(f"  Storage: {summary['avg_storage_utilization']:.1f}% avg, "
                  f"{summary['max_storage_utilization']:.1f}% peak")

        print("\n✅ BENCHMARK COMPLETED!")
        print("=" * 60)


def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='CloudSim Performance Benchmark')
    parser.add_argument('--test', choices=['file_transfer', 'concurrent', 'network', 'full'],
                       default='full', help='Specific test to run')
    parser.add_argument('--nodes', type=int, default=5, help='Number of nodes in test network')
    parser.add_argument('--output', help='Output file for results')

    args = parser.parse_args()

    benchmark = CloudSimBenchmark()

    if args.test == 'full':
        results = benchmark.run_full_benchmark()
    else:
        # Create network
        benchmark.create_test_network(args.nodes)

        if args.test == 'file_transfer':
            results = {'file_transfer_benchmark': benchmark.benchmark_file_transfers()}
        elif args.test == 'concurrent':
            results = {'concurrent_transfer_benchmark': benchmark.benchmark_concurrent_transfers()}
        elif args.test == 'network':
            results = {'network_utilization_benchmark': benchmark.benchmark_network_utilization()}

    # Save results if output specified
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        print(f"\n💾 Results saved to: {args.output}")


if __name__ == "__main__":
    main()


