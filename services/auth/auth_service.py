import grpc
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

# Import generated protobuf code
from generated import cloud_storage_pb2 as pb2
from generated.cloud_storage_pb2_grpc import AuthServiceServicer
from generated.cloud_storage_pb2 import (
    Status, AuthResponse, OtpResponse, TokenValidation, UserInfo
)

# Import database and models
from .database import db
from .models import UserCreate, TokenData
from .config import (
    verify_token, create_access_token, create_refresh_token,
    ACCESS_TOKEN_EXPIRE_MINUTES, REFRESH_TOKEN_EXPIRE_DAYS,
    TOKEN_TYPE_ACCESS, TOKEN_TYPE_REFRESH
)

# Configure logging
logger = logging.getLogger(__name__)

class AuthService(AuthServiceServicer):
    """Implementation of the AuthService gRPC service."""
    
    def _get_user_agent(self, context) -> str:
        """Extract user agent from the gRPC context."""
        metadata = dict(context.invocation_metadata())
        return metadata.get('user-agent', 'unknown')
    
    def _get_ip_address(self, context) -> str:
        """Extract IP address from the gRPC context."""
        # This is a simplified version - in production, you'd want to properly
        # handle proxies and other edge cases
        peer = context.peer()
        return peer.split(':')[1] if ':' in peer else peer
    
    def _create_auth_response(self, user_id: str) -> AuthResponse:
        """Create an authentication response with tokens."""
        # Create a new session
        session = db.create_session(
            user_id=user_id,
            user_agent=self._get_user_agent(context),
            ip_address=self._get_ip_address(context)
        )
        
        return AuthResponse(
            status=Status(success=True, message="Authentication successful"),
            auth_token=session.access_token,
            refresh_token=session.refresh_token,
            expires_in=int((session.expires_at - datetime.utcnow()).total_seconds())
        )
    
    def Register(self, request, context):
        """Handle user registration."""
        try:
            # Check if username or email already exists
            if db.get_user(request.username):
                context.set_code(grpc.StatusCode.ALREADY_EXISTS)
                return AuthResponse(
                    status=Status(
                        success=False,
                        message="Username already exists",
                        error="USERNAME_EXISTS"
                    )
                )
            
            # Create new user
            user_data = {
                "username": request.username,
                "email": request.email,
                "password": request.password,
                "full_name": request.full_name
            }
            
            user = db.create_user(user_data)
            logger.info(f"New user registered: {user.username} ({user.id})")
            
            # Create and return auth response
            return self._create_auth_response(user.id)
            
        except ValueError as e:
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            return AuthResponse(
                status=Status(success=False, message=str(e))
            )
        except Exception as e:
            logger.error(f"Registration error: {e}", exc_info=True)
            context.set_code(grpc.StatusCode.INTERNAL)
            return AuthResponse(
                status=Status(success=False, message="Internal server error")
            )
    
    def Login(self, request, context):
        """Handle user login."""
        try:
            # Get user by username
            user = db.get_user(request.username)
            if not user:
                context.set_code(grpc.StatusCode.UNAUTHENTICATED)
                return AuthResponse(
                    status=Status(
                        success=False,
                        message="Invalid username or password",
                        error="INVALID_CREDENTIALS"
                    )
            
            # Verify password
            if not user.verify_password(request.password):
                context.set_code(grpc.StatusCode.UNAUTHENTICATED)
                return AuthResponse(
                    status=Status(
                        success=False,
                        message="Invalid username or password",
                        error="INVALID_CREDENTIALS"
                    )
            
            # Check if user is disabled
            if user.disabled:
                context.set_code(grpc.StatusCode.PERMISSION_DENIED)
                return AuthResponse(
                    status=Status(
                        success=False,
                        message="Account is disabled",
                        error="ACCOUNT_DISABLED"
                    )
            
            logger.info(f"User logged in: {user.username} ({user.id})")
            
            # Create and return auth response
            return self._create_auth_response(user.id)
            
        except Exception as e:
            logger.error(f"Login error: {e}", exc_info=True)
            context.set_code(grpc.StatusCode.INTERNAL)
            return AuthResponse(
                status=Status(success=False, message="Internal server error")
            )
    
    def SendOtp(self, request, context):
        """Send OTP to the provided email."""
        try:
            # In a real application, you would send the OTP via email
            # For this example, we'll just log it
            otp = db.create_otp(request.email)
            
            logger.info(f"OTP generated for {request.email}: {otp.otp}")
            
            return OtpResponse(
                status=Status(success=True, message="OTP sent successfully"),
                otp_id=otp.id,
                expires_in=int((otp.expires_at - datetime.utcnow()).total_seconds())
            )
            
        except Exception as e:
            logger.error(f"Send OTP error: {e}", exc_info=True)
            context.set_code(grpc.StatusCode.INTERNAL)
            return OtpResponse(
                status=Status(success=False, message="Failed to send OTP")
            )
    
    def VerifyOtp(self, request, context):
        """Verify OTP and authenticate user."""
        try:
            # In a real application, you would have a way to map OTP to user
            # For this example, we'll just check if the OTP is valid
            is_valid = db.verify_otp(request.email, request.otp)
            
            if not is_valid:
                context.set_code(grpc.StatusCode.UNAUTHENTICATED)
                return AuthResponse(
                    status=Status(
                        success=False,
                        message="Invalid or expired OTP",
                        error="INVALID_OTP"
                    )
            
            # For this example, we'll create a user if they don't exist
            user = db.get_user_by_email(request.email)
            if not user:
                # In a real app, you'd have a proper user creation flow
                user_data = {
                    "username": request.email.split('@')[0],
                    "email": request.email,
                    "password": "temporary_password_123",  # In real app, prompt for password
                    "full_name": "",
                    "is_verified": True
                }
                user = db.create_user(user_data)
            
            logger.info(f"OTP verified for user: {user.username} ({user.id})")
            
            # Create and return auth response
            return self._create_auth_response(user.id)
            
        except Exception as e:
            logger.error(f"Verify OTP error: {e}", exc_info=True)
            context.set_code(grpc.StatusCode.INTERNAL)
            return AuthResponse(
                status=Status(success=False, message="Failed to verify OTP")
            )
    
    def ValidateToken(self, request, context):
        """Validate an authentication token."""
        try:
            token = request.token
            if not token:
                return TokenValidation(valid=False)
            
            # Verify token
            payload = verify_token(token)
            if not payload:
                return TokenValidation(valid=False)
            
            # Check if token is expired
            exp = payload.get("exp")
            if exp and datetime.utcnow() > datetime.fromtimestamp(exp):
                return TokenValidation(valid=False)
            
            # Get user
            user_id = payload.get("sub")
            user = db.get_user_by_id(user_id) if user_id else None
            
            if not user or user.disabled:
                return TokenValidation(valid=False)
            
            # Check if this is a session token
            token_type = payload.get("type")
            if token_type == TOKEN_TYPE_ACCESS:
                session = db.get_session_by_token(token, "access")
                if not session or session.is_expired() or not session.is_active:
                    return TokenValidation(valid=False)
            
            return TokenValidation(
                valid=True,
                user_id=user.id,
                username=user.username,
                expires_at=exp
            )
            
        except Exception as e:
            logger.error(f"Token validation error: {e}", exc_info=True)
            return TokenValidation(valid=False)
    
    def GetUserInfo(self, request, context):
        """Get user information."""
        try:
            # Get user by ID
            user = db.get_user_by_id(request.user_id)
            if not user:
                context.set_code(grpc.StatusCode.NOT_FOUND)
                return UserInfo(
                    status=Status(
                        success=False,
                        message="User not found",
                        error="USER_NOT_FOUND"
                    )
            
            # Check permissions (in a real app, implement proper authorization)
            # For now, just return the user info
            return UserInfo(
                status=Status(success=True, message="User info retrieved"),
                user_id=user.id,
                username=user.username,
                email=user.email,
                full_name=user.full_name or "",
                is_verified=user.is_verified,
                created_at=user.created_at.isoformat(),
                last_login=user.last_login.isoformat() if user.last_login else ""
            )
            
        except Exception as e:
            logger.error(f"Get user info error: {e}", exc_info=True)
            context.set_code(grpc.StatusCode.INTERNAL)
            return UserInfo(
                status=Status(success=False, message="Failed to get user info")
            )
