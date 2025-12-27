import os
import logging
import grpc
from concurrent import futures
from dotenv import load_dotenv

# Import generated protobuf code
from generated import cloud_storage_pb2_grpc as pb2_grpc
from generated.cloud_storage_pb2 import Status, OperationStatus

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

class AuthService(pb2_grpc.AuthServiceServicer):
    """Implementation of AuthService"""
    
    def Register(self, request, context):
        logger.info(f"Register request: {request.username}")
        # TODO: Implement registration logic
        return pb2_grpc.AuthResponse(
            status=Status(success=True, message="Registration successful"),
            auth_token="dummy_token",
            refresh_token="dummy_refresh_token",
            expires_in=3600
        )
    
    def Login(self, request, context):
        logger.info(f"Login request: {request.username}")
        # TODO: Implement login logic
        return pb2_grpc.AuthResponse(
            status=Status(success=True, message="Login successful"),
            auth_token="dummy_token",
            refresh_token="dummy_refresh_token",
            expires_in=3600
        )
    
    def SendOtp(self, request, context):
        logger.info(f"Send OTP request for email: {request.email}")
        # TODO: Implement OTP sending logic
        return pb2_grpc.OtpResponse(
            status=Status(success=True, message="OTP sent successfully"),
            otp_id="dummy_otp_id",
            expires_in=300
        )
    
    def VerifyOtp(self, request, context):
        logger.info(f"Verify OTP request for email: {request.email}")
        # TODO: Implement OTP verification logic
        return pb2_grpc.AuthResponse(
            status=Status(success=True, message="OTP verified successfully"),
            auth_token="dummy_token",
            refresh_token="dummy_refresh_token",
            expires_in=3600
        )
    
    def ValidateToken(self, request, context):
        logger.info("Token validation request")
        # TODO: Implement token validation logic
        return pb2_grpc.TokenValidation(
            valid=True,
            user_id="dummy_user_id",
            username="dummy_user",
            expires_at=0
        )
    
    def GetUserInfo(self, request, context):
        logger.info(f"Get user info for user_id: {request.user_id}")
        # TODO: Implement user info retrieval
        return pb2_grpc.UserInfo(
            user_id=request.user_id,
            username="dummy_user",
            email="dummy@example.com",
            full_name="Dummy User",
            is_admin=False,
            storage_quota=5368709120,  # 5GB
            storage_used=0
        )

class FileService(pb2_grpc.FileServiceServicer):
    """Implementation of FileService"""
    
    def UploadFile(self, request_iterator, context):
        file_info = None
        file_data = bytearray()
        
        # Process the file chunks
        for chunk in request_iterator:
            if not file_info:
                file_info = {
                    'file_id': chunk.file_id or f"file_{int(time.time())}",
                    'file_name': chunk.file_name,
                    'mime_type': chunk.mime_type,
                    'file_size': chunk.file_size,
                    'total_chunks': chunk.total_chunks,
                }
                logger.info(f"Starting upload: {file_info}")
            
            file_data.extend(chunk.content)
            logger.debug(f"Received chunk {chunk.chunk_number + 1}/{chunk.total_chunks} for {file_info['file_id']}")
        
        # TODO: Save the file and update metadata
        logger.info(f"Upload completed for {file_info['file_id']}, size: {len(file_data)} bytes")
        
        return pb2_grpc.UploadResponse(
            status=Status(success=True, message="File uploaded successfully"),
            file_id=file_info['file_id'],
            bytes_received=len(file_data),
            file_url=f"/files/{file_info['file_id']}"
        )
    
    def DownloadFile(self, request, context):
        logger.info(f"Download request for file_id: {request.file_id}")
        # TODO: Implement file download logic
        # This is a simplified example - in a real implementation, you would:
        # 1. Verify the user has permission to access the file
        # 2. Read the file in chunks and yield them
        
        # Example: Yield a single chunk for demonstration
        yield pb2_grpc.FileChunk(
            file_id=request.file_id,
            file_name="example.txt",
            content=b"This is a sample file content.",
            chunk_number=0,
            total_chunks=1,
            mime_type="text/plain",
            file_size=28
        )
    
    def DeleteFile(self, request, context):
        logger.info(f"Delete request for file_id: {request.file_id}")
        # TODO: Implement file deletion logic
        return OperationStatus(
            success=True,
            message=f"File {request.file_id} deleted successfully",
            operation_id=f"del_{request.file_id}"
        )
    
    def ListFiles(self, request, context):
        logger.info(f"List files request for user_id: {request.user_id}")
        # TODO: Implement file listing logic
        return pb2_grpc.FileList(
            files=[],
            total_count=0,
            total_size=0
        )
    
    def GetFileInfo(self, request, context):
        logger.info(f"Get file info for file_id: {request.file_id}")
        # TODO: Implement file info retrieval
        return pb2_grpc.FileInfo(
            file_id=request.file_id,
            file_name="example.txt",
            mime_type="text/plain",
            size=28,
            checksum="dummy_checksum"
        )
    
    def CreateDirectory(self, request, context):
        logger.info(f"Create directory: {request.path}/{request.name} for user {request.user_id}")
        # TODO: Implement directory creation
        return OperationStatus(
            success=True,
            message=f"Directory {request.name} created successfully",
            operation_id=f"mkdir_{request.user_id}_{request.name}"
        )

class StorageService(pb2_grpc.StorageServiceServicer):
    """Implementation of StorageService"""
    
    def GetStorageUsage(self, request, context):
        logger.info(f"Get storage usage for user: {request.user_id}")
        # TODO: Implement storage usage calculation
        return pb2_grpc.StorageInfo(
            total_space=5368709120,  # 5GB
            used_space=0,
            available_space=5368709120,
            file_count=0
        )
    
    def GetNodeStatus(self, request, context):
        logger.info(f"Get node status for node: {request.node_id}")
        # TODO: Implement node status retrieval
        return pb2_grpc.NodeStatus(
            node_id=request.node_id or "node1",
            status="ONLINE",
            total_space=10737418240,  # 10GB
            used_space=0,
            active_connections=1,
            host="localhost",
            port=50051
        )
    
    def AddStorageNode(self, request, context):
        logger.info(f"Add storage node: {request.host}:{request.port}")
        # TODO: Implement node addition logic
        return OperationStatus(
            success=True,
            message=f"Node {request.host}:{request.port} added successfully",
            operation_id=f"add_node_{request.host}_{request.port}"
        )
    
    def RemoveStorageNode(self, request, context):
        logger.info(f"Remove storage node: {request.node_id}")
        # TODO: Implement node removal logic
        return OperationStatus(
            success=True,
            message=f"Node {request.node_id} removed successfully",
            operation_id=f"remove_node_{request.node_id}"
        )
    
    def RebalanceStorage(self, request, context):
        logger.info(f"Rebalance storage for node: {request.node_id or 'all'}")
        # TODO: Implement storage rebalancing
        return OperationStatus(
            success=True,
            message=f"Storage rebalancing completed for node {request.node_id or 'all'}",
            operation_id=f"rebalance_{request.node_id or 'all'}"
        )

def serve():
    # Read configuration from environment variables
    server_address = os.getenv('GRPC_SERVER_ADDRESS', '[::]:50051')
    max_workers = int(os.getenv('GRPC_MAX_WORKERS', '10'))
    
    # Create gRPC server
    server = grpc.server(
        futures.ThreadPoolExecutor(max_workers=max_workers),
        options=[
            ('grpc.max_send_message_length', 100 * 1024 * 1024),  # 100MB
            ('grpc.max_receive_message_length', 100 * 1024 * 1024)  # 100MB
        ]
    )
    
    # Add services to the server
    pb2_grpc.add_AuthServiceServicer_to_server(AuthService(), server)
    pb2_grpc.add_FileServiceServicer_to_server(FileService(), server)
    pb2_grpc.add_StorageServiceServicer_to_server(StorageService(), server)
    
    # Start the server
    server.add_insecure_port(server_address)
    server.start()
    
    logger.info(f"Server started on {server_address}")
    
    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        logger.info("Shutting down server...")
        server.stop(0)
        logger.info("Server stopped")

if __name__ == '__main__':
    serve()
