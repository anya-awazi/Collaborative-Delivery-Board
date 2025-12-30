import grpc
import os
import sys
from typing import Optional, Tuple, Dict, Any
from datetime import datetime, timedelta

# Add the generated directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'generated'))

# Import the generated protobuf and gRPC code
try:
    import cloud_storage_pb2
    import cloud_storage_pb2_grpc
    from google.protobuf.timestamp_pb2 import Timestamp
    from google.protobuf.empty_pb2 import Empty
    from google.protobuf.json_format import MessageToDict
    
    # Define the protobuf message types for type hints
    from cloud_storage_pb2 import (
        RegisterRequest, LoginRequest, OtpRequest, OtpVerification,
        TokenRequest, TokenValidation, AuthResponse, UserInfo, Status
    )
except ImportError:
    # Create dummy classes for type hints if the generated files are not available
    class DummyMessage: pass
    
    cloud_storage_pb2 = type('DummyProto', (), {
        'RegisterRequest': DummyMessage,
        'LoginRequest': DummyMessage,
        'OtpRequest': DummyMessage,
        'OtpVerification': DummyMessage,
        'TokenRequest': DummyMessage,
        'TokenValidation': DummyMessage,
        'AuthResponse': DummyMessage,
        'UserInfo': DummyMessage,
        'Status': DummyMessage,
    })
    
    cloud_storage_pb2_grpc = type('DummyGrpc', (), {
        'AuthServiceStub': type('DummyStub', (), {})
    })
    
    class Timestamp: pass
    class Empty: pass


class AuthClient:
    """
    gRPC client for handling authentication with the cloud storage service.
    
    This client provides methods for user registration, login, OTP verification,
    and token validation.
    """
    
    def __init__(self, host: str = 'localhost', port: int = 50051, secure: bool = False):
        """
        Initialize the authentication client.
        
        Args:
            host: The server hostname or IP address
            port: The server port
            secure: Whether to use a secure connection (TLS/SSL)
        """
        self.host = host
        self.port = port
        self.secure = secure
        self.channel = None
        self.stub = None
        self.auth_token = None
        self.refresh_token = None
        self.token_expiry = None
        self.user_info = None
        
    def connect(self) -> bool:
        """
        Establish a connection to the authentication service.
        
        Returns:
            bool: True if the connection was successful, False otherwise
        """
        try:
            if self.secure:
                # For production, you should use proper SSL/TLS certificates
                credentials = grpc.ssl_channel_credentials()
                self.channel = grpc.secure_channel(
                    f"{self.host}:{self.port}",
                    credentials
                )
            else:
                # For development/testing only
                self.channel = grpc.insecure_channel(f"{self.host}:{self.port}")
            
            # Create the gRPC stub
            self.stub = cloud_storage_pb2_grpc.AuthServiceStub(self.channel)
            return True
            
        except Exception as e:
            print(f"Failed to connect to auth service: {e}")
            return False
    
    def close(self):
        """Close the gRPC channel."""
        if self.channel:
            self.channel.close()
    
    def __enter__(self):
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
    
    def _get_metadata(self) -> list:
        """Get the authorization metadata for authenticated requests."""
        if not self.auth_token:
            return []
        return [('authorization', f'Bearer {self.auth_token}')]
    
    def register(
        self,
        username: str,
        email: str,
        password: str,
        full_name: str
    ) -> Tuple[bool, str]:
        """
        Register a new user.
        
        Args:
            username: The desired username
            email: User's email address
            password: User's password
            full_name: User's full name
            
        Returns:
            Tuple[bool, str]: (success, message)
        """
        try:
            request = RegisterRequest(
                username=username,
                email=email,
                password=password,
                full_name=full_name
            )
            
            response = self.stub.Register(request)
            
            if response.status.success:
                return True, "Registration successful"
            else:
                return False, response.status.message or "Registration failed"
                
        except grpc.RpcError as e:
            return False, f"RPC error: {e.details()}"
        except Exception as e:
            return False, f"An error occurred: {str(e)}"
    
    def login(self, username: str, password: str) -> Tuple[bool, str]:
        """
        Log in a user with username and password.
        
        Args:
            username: The username
            password: The password
            
        Returns:
            Tuple[bool, str]: (success, message)
        """
        try:
            request = LoginRequest(
                username=username,
                password=password
            )
            
            response = self.stub.Login(request)
            
            if response.status.success:
                # Store the authentication tokens
                self.auth_token = response.auth_token
                self.refresh_token = response.refresh_token
                
                # Calculate token expiry time (default to 1 hour if not provided)
                expires_in = response.expires_in or 3600
                self.token_expiry = datetime.utcnow() + timedelta(seconds=expires_in)
                
                # Store user info if available
                if response.HasField('user_info'):
                    self.user_info = MessageToDict(
                        response.user_info,
                        preserving_proto_field_name=True
                    )
                
                return True, "Login successful"
            else:
                return False, response.status.message or "Login failed"
                
        except grpc.RpcError as e:
            return False, f"RPC error: {e.details()}"
        except Exception as e:
            return False, f"An error occurred: {str(e)}"
    
    def send_otp(self, email: str) -> Tuple[bool, str]:
        """
        Send an OTP (One-Time Password) to the specified email.
        
        Args:
            email: The email address to send the OTP to
            
        Returns:
            Tuple[bool, str]: (success, message)
        """
        try:
            request = OtpRequest(email=email)
            response = self.stub.SendOtp(request)
            
            if response.status.success:
                return True, f"OTP sent to {email}"
            else:
                return False, response.status.message or "Failed to send OTP"
                
        except grpc.RpcError as e:
            return False, f"RPC error: {e.details()}"
        except Exception as e:
            return False, f"An error occurred: {str(e)}"
    
    def verify_otp(self, email: str, otp: str) -> Tuple[bool, str]:
        """
        Verify an OTP (One-Time Password).
        
        Args:
            email: The email address the OTP was sent to
            otp: The OTP to verify
            
        Returns:
            Tuple[bool, str]: (success, message)
        """
        try:
            request = OtpVerification(email=email, otp=otp)
            response = self.stub.VerifyOtp(request)
            
            if response.status.success:
                # Store the authentication tokens if provided
                if response.auth_token:
                    self.auth_token = response.auth_token
                    self.refresh_token = response.refresh_token
                    
                    # Calculate token expiry time
                    expires_in = response.expires_in or 3600
                    self.token_expiry = datetime.utcnow() + timedelta(seconds=expires_in)
                    
                    # Store user info if available
                    if response.HasField('user_info'):
                        self.user_info = MessageToDict(
                            response.user_info,
                            preserving_proto_field_name=True
                        )
                
                return True, "OTP verified successfully"
            else:
                return False, response.status.message or "OTP verification failed"
                
        except grpc.RpcError as e:
            return False, f"RPC error: {e.details()}"
        except Exception as e:
            return False, f"An error occurred: {str(e)}"
    
    def validate_token(self, token: str = None) -> Tuple[bool, Dict[str, Any]]:
        """
        Validate an authentication token.
        
        Args:
            token: The token to validate (uses the current auth token if None)
            
        Returns:
            Tuple[bool, Dict]: (is_valid, token_info)
        """
        if not token and not self.auth_token:
            return False, {"error": "No token provided and no active session"}
            
        token_to_validate = token or self.auth_token
        
        try:
            request = TokenRequest(token=token_to_validate)
            response = self.stub.ValidateToken(
                request,
                metadata=self._get_metadata()
            )
            
            if response.valid:
                token_info = {
                    "user_id": response.user_id,
                    "username": response.username,
                    "expires_at": datetime.utcfromtimestamp(response.expires_at)
                }
                return True, token_info
            else:
                return False, {"error": "Invalid or expired token"}
                
        except grpc.RpcError as e:
            return False, {"error": f"RPC error: {e.details()}"}
        except Exception as e:
            return False, {"error": f"An error occurred: {str(e)}"}
    
    def get_user_info(self, user_id: str = None) -> Tuple[bool, Dict[str, Any]]:
        """
        Get information about a user.
        
        Args:
            user_id: The ID of the user to get info for (current user if None)
            
        Returns:
            Tuple[bool, Dict]: (success, user_info)
        """
        if not user_id and not self.auth_token:
            return False, {"error": "No user ID provided and no active session"}
            
        try:
            request = UserRequest(user_id=user_id or self.user_info.get('user_id') if self.user_info else None)
            response = self.stub.GetUserInfo(
                request,
                metadata=self._get_metadata()
            )
            
            if response.status.success:
                user_info = MessageToDict(
                    response,
                    preserving_proto_field_name=True
                )
                return True, user_info
            else:
                return False, {"error": response.status.message or "Failed to get user info"}
                
        except grpc.RpcError as e:
            return False, {"error": f"RPC error: {e.details()}"}
        except Exception as e:
            return False, {"error": f"An error occurred: {str(e)}"}
    
    def is_authenticated(self) -> bool:
        """Check if the client has a valid authentication token."""
        if not self.auth_token:
            return False
            
        if self.token_expiry and datetime.utcnow() >= self.token_expiry:
            return False
            
        # Optionally validate the token with the server
        # For performance, you might want to skip this in production
        # and rely on the local expiry time
        is_valid, _ = self.validate_token()
        return is_valid


# Example usage
if __name__ == "__main__":
    # Create a client instance
    with AuthClient(host='localhost', port=50051) as client:
        # Example: Register a new user
        success, message = client.register(
            username="testuser",
            email="test@example.com",
            password="securepassword123",
            full_name="Test User"
        )
        print(f"Registration: {'Success' if success else 'Failed'} - {message}")
        
        # Example: Login
        if success:
            success, message = client.login("testuser", "securepassword123")
            print(f"Login: {'Success' if success else 'Failed'} - {message}")
            
            if success:
                # Example: Get user info
                success, user_info = client.get_user_info()
                if success:
                    print(f"User Info: {user_info}")
                
                # Example: Validate token
                is_valid, token_info = client.validate_token()
                print(f"Token valid: {is_valid}")
                if is_valid:
                    print(f"Token info: {token_info}")
                
                # Example: Send and verify OTP
                if client.user_info and 'email' in client.user_info:
                    email = client.user_info['email']
                    success, message = client.send_otp(email)
                    print(f"Send OTP: {'Success' if success else 'Failed'} - {message}")
                    
                    # In a real app, you would get the OTP from user input
                    otp = input(f"Enter OTP sent to {email}: ")
                    success, message = client.verify_otp(email, otp)
                    print(f"Verify OTP: {'Success' if success else 'Failed'} - {message}")
