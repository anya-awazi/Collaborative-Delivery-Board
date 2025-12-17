#!/usr/bin/env python3
"""
Performance Test Suite for CloudSim Storage Virtual Network

This script benchmarks various performance aspects of the cloud simulation:
- File transfer throughput and latency
- Network utilization under load
- Storage allocation performance
- Concurrent transfer handling
- Memory and CPU usage patterns
"""

import time
import psutil
import threading
import multiprocessing
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Tuple
import statistics
import json
from datetime import datetime

from storage_virtual_node import StorageVirtualNode
from storage_virtual_network import StorageVirtualNetwork


class PerformanceTestSuite:
    """Comprehensive performance testing suite for CloudSim"""

    def __init__(self):
        self.network = None
        self.test_results = {}
        self.process = psutil.Process()

    def setup_test_network(self, num_nodes: int = 5) -> StorageVirtualNetwork:
        """Create a test network with specified number of nodes"""
        network = StorageVirtualNetwork()

        # Create nodes with varying capacities
        for i in range(num_nodes):
            node = StorageVirtualNode(
                node_id=f"node_{i}",
                cpu_capacity=4 + i,  # 4-8 vCPUs
                memory_capacity=8 + i * 2,  # 8-16 GB
                storage_capacity=100 + i * 50,  # 100-300 GB
                bandwidth=100 + i * 50  # 100-300 Mbps
            )
            network.add_node(node)

        # Connect all nodes in a mesh topology
        for i in range(num_nodes):
            for j in range(i + 1, num_nodes):
                bandwidth = min(200, 100 + abs(i - j) * 20)  # Varying bandwidths
                network.connect_nodes(f"node_{i}", f"node_{j}", bandwidth)

        self.network = network
        return network

    def measure_memory_usage(self) -> Dict[str, float]:
        """Measure current memory usage"""
        mem = self.process.memory_info()
        return {
            'rss_mb': mem.rss / 1024 / 1024,
            'vms_mb': mem.vms / 1024 / 1024,
            'percent': self.process.memory_percent()
        }

    def measure_cpu_usage(self, interval: float = 0.1) -> float:
        """Measure CPU usage over an interval"""
        return self.process.cpu_percent(interval=interval)

    def test_file_transfer_performance(self, file_sizes_mb: List[int], num_transfers: int = 10) -> Dict:
        """Test file transfer performance for different file sizes"""
        print(f"\n{'='*60}")
        print("FILE TRANSFER PERFORMANCE TEST")
        print(f"{'='*60}")

        results = {
            'file_sizes_mb': file_sizes_mb,
            'transfers_per_size': num_transfers,
            'results': {}
        }

        for size_mb in file_sizes_mb:
            print(f"\nTesting {size_mb}MB file transfers...")
            transfer_times = []
            throughput_values = []

            for i in range(num_transfers):
                # Select random source and target nodes
                source_node = f"node_{i % len(self.network.nodes)}"
                target_node = f"node_{(i + 1) % len(self.network.nodes)}"

                file_size_bytes = size_mb * 1024 * 1024

                # Start timing
                start_time = time.time()

                # Initiate transfer
                transfer = self.network.initiate_file_transfer(
                    source_node, target_node, f"test_file_{size_mb}mb_{i}.dat", file_size_bytes
                )

                if transfer:
                    file_id = transfer.file_id

                    # Process transfer in chunks
                    total_chunks = len(transfer.chunks)
                    chunks_processed = 0

                    while chunks_processed < total_chunks:
                        chunks_this_step, complete = self.network.process_file_transfer(
                            source_node, target_node, file_id, chunks_per_step=5
                        )
                        chunks_processed += chunks_this_step

                        if not complete and chunks_this_step == 0:
                            break

                    if transfer.status.name == 'COMPLETED':
                        end_time = time.time()
                        transfer_time = end_time - start_time
                        throughput = file_size_bytes / transfer_time / (1024 * 1024)  # MB/s

                        transfer_times.append(transfer_time)
                        throughput_values.append(throughput)
                        print(".1f")
                    else:
                        print(f"  Transfer {i+1} failed")
                else:
                    print(f"  Transfer {i+1} initiation failed - insufficient storage")

            if transfer_times:
                results['results'][size_mb] = {
                    'avg_transfer_time_sec': statistics.mean(transfer_times),
                    'min_transfer_time_sec': min(transfer_times),
                    'max_transfer_time_sec': max(transfer_times),
                    'std_transfer_time_sec': statistics.stdev(transfer_times) if len(transfer_times) > 1 else 0,
                    'avg_throughput_mbps': statistics.mean(throughput_values),
                    'min_throughput_mbps': min(throughput_values),
                    'max_throughput_mbps': max(throughput_values),
                    'successful_transfers': len(transfer_times),
                    'total_transfers': num_transfers
                }

                print(f"  Average throughput: {statistics.mean(throughput_values):.2f} MB/s")
                print(f"  Success rate: {len(transfer_times)}/{num_transfers}")

        return results

    def test_concurrent_transfers(self, num_concurrent: int = 20, file_size_mb: int = 50) -> Dict:
        """Test performance under concurrent transfer load"""
        print(f"\n{'='*60}")
        print("CONCURRENT TRANSFER PERFORMANCE TEST")
        print(f"{'='*60}")
        print(f"Testing {num_concurrent} concurrent {file_size_mb}MB transfers...")

        results = {
            'num_concurrent_transfers': num_concurrent,
            'file_size_mb': file_size_mb,
            'transfer_times': [],
            'throughput_values': [],
            'start_time': time.time()
        }

        def single_transfer(transfer_id: int):
            source_node = f"node_{transfer_id % len(self.network.nodes)}"
            target_node = f"node_{(transfer_id + 1) % len(self.network.nodes)}"

            file_size_bytes = file_size_mb * 1024 * 1024

            start_time = time.time()
            transfer = self.network.initiate_file_transfer(
                source_node, target_node, f"concurrent_file_{transfer_id}.dat", file_size_bytes
            )

            if transfer:
                file_id = transfer.file_id
                total_chunks = len(transfer.chunks)
                chunks_processed = 0

                while chunks_processed < total_chunks:
                    chunks_this_step, complete = self.network.process_file_transfer(
                        source_node, target_node, file_id, chunks_per_step=3
                    )
                    chunks_processed += chunks_this_step

                    if not complete and chunks_this_step == 0:
                        break

                if transfer.status.name == 'COMPLETED':
                    end_time = time.time()
                    transfer_time = end_time - start_time
                    throughput = file_size_bytes / transfer_time / (1024 * 1024)  # MB/s
                    return transfer_time, throughput
            return None, None

        # Execute concurrent transfers
        with ThreadPoolExecutor(max_workers=num_concurrent) as executor:
            futures = [executor.submit(single_transfer, i) for i in range(num_concurrent)]

            successful_transfers = 0
            for future in as_completed(futures):
                transfer_time, throughput = future.result()
                if transfer_time is not None:
                    results['transfer_times'].append(transfer_time)
                    results['throughput_values'].append(throughput)
                    successful_transfers += 1

        results['end_time'] = time.time()
        results['total_duration'] = results['end_time'] - results['start_time']
        results['successful_transfers'] = successful_transfers
        results['success_rate'] = successful_transfers / num_concurrent

        if results['transfer_times']:
            results['avg_transfer_time'] = statistics.mean(results['transfer_times'])
            results['avg_throughput'] = statistics.mean(results['throughput_values'])
            results['total_throughput'] = sum(results['throughput_values'])

            print(f"Total duration: {results['total_duration']:.2f} seconds")
            print(f"Average transfer time: {results['avg_transfer_time']:.2f} seconds")
            print(f"Average throughput per transfer: {results['avg_throughput']:.2f} MB/s")
            print(f"Total network throughput: {results['total_throughput']:.2f} MB/s")
            print(f"Success rate: {results['success_rate']:.1%}")

        return results

    def test_network_utilization(self, duration_sec: int = 60) -> Dict:
        """Test network utilization over time"""
        print(f"\n{'='*60}")
        print("NETWORK UTILIZATION TEST")
        print(f"{'='*60}")
        print(f"Monitoring network utilization for {duration_sec} seconds...")

        results = {
            'duration_sec': duration_sec,
            'measurements': [],
            'timestamps': []
        }

        start_time = time.time()

        # Start background transfers to generate load
        def background_transfers():
            for i in range(50):  # Continuous transfers
                if time.time() - start_time > duration_sec:
                    break

                source_node = f"node_{i % len(self.network.nodes)}"
                target_node = f"node_{(i + 1) % len(self.network.nodes)}"

                transfer = self.network.initiate_file_transfer(
                    source_node, target_node, f"bg_file_{i}.dat", 10 * 1024 * 1024  # 10MB files
                )

                if transfer:
                    file_id = transfer.file_id
                    total_chunks = len(transfer.chunks)
                    chunks_processed = 0

                    while chunks_processed < total_chunks and time.time() - start_time <= duration_sec:
                        chunks_this_step, complete = self.network.process_file_transfer(
                            source_node, target_node, file_id, chunks_per_step=2
                        )
                        chunks_processed += chunks_this_step

                        if not complete and chunks_this_step == 0:
                            break

        # Start background transfers in a separate thread
        transfer_thread = threading.Thread(target=background_transfers, daemon=True)
        transfer_thread.start()

        # Monitor utilization
        while time.time() - start_time < duration_sec:
            stats = self.network.get_network_stats()
            mem_usage = self.measure_memory_usage()
            cpu_usage = self.measure_cpu_usage(0.1)

            measurement = {
                'timestamp': time.time() - start_time,
                'network_stats': stats,
                'memory_usage': mem_usage,
                'cpu_percent': cpu_usage
            }

            results['measurements'].append(measurement)
            results['timestamps'].append(measurement['timestamp'])

            time.sleep(1)  # Sample every second

        transfer_thread.join(timeout=1)

        # Calculate averages
        if results['measurements']:
            avg_bandwidth_util = statistics.mean(m['network_stats']['bandwidth_utilization']
                                               for m in results['measurements'])
            avg_cpu = statistics.mean(m['cpu_percent'] for m in results['measurements'])
            avg_memory = statistics.mean(m['memory_usage']['rss_mb'] for m in results['measurements'])

            results['summary'] = {
                'avg_bandwidth_utilization': avg_bandwidth_util,
                'avg_cpu_percent': avg_cpu,
                'avg_memory_mb': avg_memory,
                'max_bandwidth_utilization': max(m['network_stats']['bandwidth_utilization']
                                               for m in results['measurements']),
                'max_memory_mb': max(m['memory_usage']['rss_mb'] for m in results['measurements'])
            }

            print(f"Average bandwidth utilization: {avg_bandwidth_util:.1f}%")
            print(f"Average CPU usage: {avg_cpu:.1f}%")
            print(f"Average memory usage: {avg_memory:.1f} MB")

        return results

    def run_full_test_suite(self) -> Dict:
        """Run the complete performance test suite"""
        print("CLOUDSIM PERFORMANCE TEST SUITE")
        print("=" * 80)
        print(f"Test started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"System: {multiprocessing.cpu_count()} CPU cores")

        # Setup test network
        print("\nSetting up test network...")
        self.setup_test_network(num_nodes=6)

        # Run individual tests
        test_start_time = time.time()

        self.test_results['file_transfer_test'] = self.test_file_transfer_performance(
            file_sizes_mb=[1, 10, 50, 100], num_transfers=5
        )

        self.test_results['concurrent_transfer_test'] = self.test_concurrent_transfers(
            num_concurrent=15, file_size_mb=25
        )

        self.test_results['network_utilization_test'] = self.test_network_utilization(
            duration_sec=30  # Shorter duration for demo
        )

        test_end_time = time.time()
        self.test_results['total_test_duration'] = test_end_time - test_start_time

        # Save results to file
        results_file = f"performance_results_{int(time.time())}.json"
        with open(results_file, 'w') as f:
            json.dump(self.test_results, f, indent=2, default=str)

        print(f"\n{'='*80}")
        print("PERFORMANCE TEST SUITE COMPLETED")
        print(f"{'='*80}")
        print(f"Total test duration: {self.test_results['total_test_duration']:.2f} seconds")
        print(f"Results saved to: {results_file}")

        return self.test_results

    def print_summary_report(self):
        """Print a summary of test results"""
        if not self.test_results:
            print("No test results available. Run tests first.")
            return

        print("\n" + "="*80)
        print("PERFORMANCE TEST SUMMARY REPORT")
        print("="*80)

        # File transfer summary
        if 'file_transfer_test' in self.test_results:
            ft_results = self.test_results['file_transfer_test']
            print("\n📁 FILE TRANSFER PERFORMANCE:")
            for size, data in ft_results['results'].items():
                print(f"  {size}MB files: {data['avg_throughput_mbps']:.2f} MB/s avg, "
                      f"{data['successful_transfers']}/{data['total_transfers']} successful")

        # Concurrent transfer summary
        if 'concurrent_transfer_test' in self.test_results:
            ct_results = self.test_results['concurrent_transfer_test']
            print("\n🔄 CONCURRENT TRANSFER PERFORMANCE:")
            print(f"  {ct_results['num_concurrent_transfers']} concurrent transfers")
            print(f"  Success rate: {ct_results['success_rate']:.1%}")
            if 'avg_throughput' in ct_results:
                print(f"  Average throughput: {ct_results['avg_throughput']:.2f} MB/s per transfer")
                print(f"  Total throughput: {ct_results['total_throughput']:.2f} MB/s")

        # Network utilization summary
        if 'network_utilization_test' in self.test_results:
            nu_results = self.test_results['network_utilization_test']
            if 'summary' in nu_results:
                summary = nu_results['summary']
                print("\n🌐 NETWORK UTILIZATION:")
                print(f"  Average bandwidth utilization: {summary['avg_bandwidth_utilization']:.1f}%")
                print(f"  Peak bandwidth utilization: {summary['max_bandwidth_utilization']:.1f}%")
                print(f"  Average CPU usage: {summary['avg_cpu_percent']:.1f}%")
                print(f"  Peak memory usage: {summary['avg_memory_mb']:.1f} MB")

        print(f"\n⏱️  Total test duration: {self.test_results['total_test_duration']:.2f} seconds")


def main():
    """Main function to run the performance tests"""
    # Create and run the test suite
    test_suite = PerformanceTestSuite()
    results = test_suite.run_full_test_suite()

    # Print summary report
    test_suite.print_summary_report()

    return results


if __name__ == "__main__":
    main()


