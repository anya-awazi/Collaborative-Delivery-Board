import socket
import json
import threading
import queue
import logging
from typing import Dict, Any, Optional, Callable

class SSkeleton:
    """
    Server Skeleton (SSkeleton) class for handling network operations and job execution.
    This class provides a framework for creating a server that can receive jobs over the network
    and execute them asynchronously.
    """
    
    def __init__(self, host: str = '0.0.0.0', port: int = 5000, max_workers: int = 5):
        """
        Initialize the SSkeleton server.
        
        Args:
            host (str): Host address to bind the server to. Defaults to '0.0.0.0' (all interfaces).
            port (int): Port number to listen on. Defaults to 5000.
            max_workers (int): Maximum number of worker threads for job execution. Defaults to 5.
        """
        self.host = host
        self.port = port
        self.max_workers = max_workers
        self.server_socket = None
        self.running = False
        self.workers = []
        self.job_queue = queue.Queue()
        self.job_handlers = {}
        self.logger = self._setup_logging()
    
    def _setup_logging(self) -> logging.Logger:
        """Set up logging configuration."""
        logger = logging.getLogger('SSkeleton')
        logger.setLevel(logging.INFO)
        
        # Create console handler and set level to INFO
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        
        # Create formatter
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        ch.setFormatter(formatter)
        
        # Add handler to logger
        logger.addHandler(ch)
        
        return logger
    
    def register_handler(self, job_type: str, handler: Callable[[Dict[str, Any]], Dict[str, Any]]) -> None:
        """
        Register a handler function for a specific job type.
        
        Args:
            job_type (str): The type of job this handler will process.
            handler (Callable): A function that takes a job dictionary and returns a result dictionary.
        """
        self.job_handlers[job_type] = handler
        self.logger.info(f"Registered handler for job type: {job_type}")
    
    def _worker_loop(self) -> None:
        """Worker thread function that processes jobs from the queue."""
        while self.running or not self.job_queue.empty():
            try:
                client_socket, job_data = self.job_queue.get(timeout=1)
                self._process_job(client_socket, job_data)
                self.job_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                self.logger.error(f"Error in worker thread: {str(e)}")
    
    def _process_job(self, client_socket: socket.socket, job_data: Dict[str, Any]) -> None:
        """
        Process a single job.
        
        Args:
            client_socket: The client socket to send the response to.
            job_data: The job data as a dictionary.
        """
        try:
            job_type = job_data.get('type')
            if not job_type:
                raise ValueError("Job type not specified")
                
            handler = self.job_handlers.get(job_type)
            if not handler:
                raise ValueError(f"No handler registered for job type: {job_type}")
            
            # Execute the handler and get the result
            result = handler(job_data)
            response = {
                'status': 'success',
                'result': result
            }
            
        except Exception as e:
            self.logger.error(f"Error processing job: {str(e)}")
            response = {
                'status': 'error',
                'error': str(e)
            }
        
        # Send the response back to the client
        try:
            response_data = json.dumps(response).encode('utf-8')
            # Send the length of the response first
            client_socket.send(len(response_data).to_bytes(4, 'big'))
            # Then send the actual response
            client_socket.sendall(response_data)
        except Exception as e:
            self.logger.error(f"Error sending response: {str(e)}")
        finally:
            client_socket.close()
    
    def _handle_client(self, client_socket: socket.socket) -> None:
        """
        Handle a client connection.
        
        Args:
            client_socket: The client socket to handle.
        """
        try:
            # First read the length of the incoming data (4 bytes)
            data_length_bytes = client_socket.recv(4)
            if not data_length_bytes:
                return
                
            data_length = int.from_bytes(data_length_bytes, 'big')
            
            # Now read the actual data
            received_data = bytearray()
            while len(received_data) < data_length:
                chunk = client_socket.recv(min(4096, data_length - len(received_data)))
                if not chunk:
                    break
                received_data.extend(chunk)
            
            if len(received_data) != data_length:
                raise ValueError("Incomplete data received")
            
            # Parse the JSON data
            job_data = json.loads(received_data.decode('utf-8'))
            
            # Add the job to the queue for processing
            self.job_queue.put((client_socket, job_data))
            
        except Exception as e:
            self.logger.error(f"Error handling client: {str(e)}")
            try:
                client_socket.close()
            except:
                pass
    
    def start(self) -> None:
        """Start the SSkeleton server and worker threads."""
        if self.running:
            self.logger.warning("Server is already running")
            return
        
        self.running = True
        
        # Create worker threads
        for i in range(self.max_workers):
            worker = threading.Thread(target=self._worker_loop, daemon=True, name=f"Worker-{i+1}")
            self.workers.append(worker)
            worker.start()
        
        # Create and configure the server socket
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(5)
        self.server_socket.settimeout(1)  # Allow for periodic checking of self.running
        
        self.logger.info(f"SSkeleton server started on {self.host}:{self.port}")
        
        try:
            while self.running:
                try:
                    client_socket, client_address = self.server_socket.accept()
                    self.logger.debug(f"Accepted connection from {client_address}")
                    self._handle_client(client_socket)
                except socket.timeout:
                    # This is expected - we use timeout to periodically check self.running
                    continue
                except Exception as e:
                    self.logger.error(f"Error accepting connection: {str(e)}")
        except KeyboardInterrupt:
            self.logger.info("Server shutdown requested via keyboard interrupt")
        except Exception as e:
            self.logger.error(f"Server error: {str(e)}")
        finally:
            self.stop()
    
    def stop(self) -> None:
        """Stop the SSkeleton server and clean up resources."""
        if not self.running:
            return
            
        self.logger.info("Shutting down SSkeleton server...")
        self.running = False
        
        # Close the server socket to unblock the accept() call
        if self.server_socket:
            try:
                self.server_socket.close()
            except Exception as e:
                self.logger.error(f"Error closing server socket: {str(e)}")
        
        # Wait for all workers to finish
        for worker in self.workers:
            worker.join(timeout=5)
        
        self.logger.info("SSkeleton server stopped")
