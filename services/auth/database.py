from typing import Dict, Optional, List, Any
import json
import os
from pathlib import Path
from datetime import datetime, timedelta
import logging

from .models import UserInDB, OTP, UserSession
from .config import (
    pwd_context, 
    get_password_hash,
    create_access_token,
    create_refresh_token,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    REFRESH_TOKEN_EXPIRE_DAYS,
    generate_otp
)

# Configure logging
logger = logging.getLogger(__name__)

class Database:
    """Simple in-memory database for authentication.
    
    In a production environment, this would be replaced with a proper database.
    """
    
    def __init__(self, data_dir: str = "data"):
        """Initialize the database."""
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        
        # In-memory storage
        self.users: Dict[str, UserInDB] = {}
        self.otps: Dict[str, OTP] = {}
        self.sessions: Dict[str, UserSession] = {}
        
        # Load data from disk if it exists
        self._load_data()
    
    def _load_data(self) -> None:
        """Load data from disk."""
        try:
            # Load users
            users_file = self.data_dir / "users.json"
            if users_file.exists():
                with open(users_file, "r") as f:
                    users_data = json.load(f)
                    self.users = {uid: UserInDB(**user) for uid, user in users_data.items()}
            
            # Load OTPs
            otps_file = self.data_dir / "otps.json"
            if otps_file.exists():
                with open(otps_file, "r") as f:
                    otps_data = json.load(f)
                    self.otps = {otp_id: OTP(**otp) for otp_id, otp in otps_data.items()}
            
            # Load sessions
            sessions_file = self.data_dir / "sessions.json"
            if sessions_file.exists():
                with open(sessions_file, "r") as f:
                    sessions_data = json.load(f)
                    self.sessions = {sid: UserSession(**session) for sid, session in sessions_data.items()}
                    
        except Exception as e:
            logger.error(f"Error loading data: {e}")
    
    def _save_data(self, data_type: str) -> None:
        """Save data to disk."""
        try:
            if data_type == "users":
                with open(self.data_dir / "users.json", "w") as f:
                    json.dump({uid: user.dict() for uid, user in self.users.items()}, f, default=str)
            elif data_type == "otps":
                with open(self.data_dir / "otps.json", "w") as f:
                    json.dump({otp_id: otp.dict() for otp_id, otp in self.otps.items()}, f, default=str)
            elif data_type == "sessions":
                with open(self.data_dir / "sessions.json", "w") as f:
                    json.dump({sid: session.dict() for sid, session in self.sessions.items()}, f, default=str)
        except Exception as e:
            logger.error(f"Error saving {data_type}: {e}")
    
    # User operations
    def get_user(self, username: str) -> Optional[UserInDB]:
        """Get a user by username."""
        for user in self.users.values():
            if user.username == username:
                return user
        return None
    
    def get_user_by_id(self, user_id: str) -> Optional[UserInDB]:
        """Get a user by ID."""
        return self.users.get(user_id)
    
    def create_user(self, user_data: Dict[str, Any]) -> UserInDB:
        """Create a new user."""
        # Check if username or email already exists
        for user in self.users.values():
            if user.username == user_data["username"]:
                raise ValueError("Username already exists")
            if user.email == user_data["email"]:
                raise ValueError("Email already registered")
        
        # Create new user
        user = UserInDB(
            **user_data,
            hashed_password=get_password_hash(user_data["password"])
        )
        
        # Save to in-memory storage
        self.users[user.id] = user
        
        # Persist to disk
        self._save_data("users")
        
        return user
    
    def update_user(self, user_id: str, user_data: Dict[str, Any]) -> Optional[UserInDB]:
        """Update a user."""
        if user_id not in self.users:
            return None
        
        # Update user data
        user = self.users[user_id]
        for key, value in user_data.items():
            if hasattr(user, key) and key != "id":
                setattr(user, key, value)
        
        # Update timestamp
        user.updated_at = datetime.utcnow()
        
        # Persist changes
        self._save_data("users")
        
        return user
    
    # OTP operations
    def create_otp(self, email: str) -> OTP:
        """Create a new OTP for the given email."""
        from .config import generate_otp, OTP_EXPIRY_MINUTES
        
        # Generate OTP
        otp_code = generate_otp()
        otp = OTP.create_new(email, otp_code, OTP_EXPIRY_MINUTES)
        
        # Save OTP
        self.otps[otp.id] = otp
        self._save_data("otps")
        
        return otp
    
    def verify_otp(self, email: str, otp_code: str) -> bool:
        """Verify an OTP."""
        # Find the most recent unused OTP for the email
        otp_to_verify = None
        for otp in self.otps.values():
            if otp.email == email and not otp.is_used and not otp.is_expired():
                otp_to_verify = otp
                break
        
        if not otp_to_verify:
            return False
        
        # Mark OTP as used
        otp_to_verify.is_used = True
        self._save_data("otps")
        
        return otp_to_verify.otp == otp_code
    
    # Session operations
    def create_session(
        self, 
        user_id: str, 
        user_agent: Optional[str] = None, 
        ip_address: Optional[str] = None
    ) -> UserSession:
        """Create a new user session."""
        from .config import create_access_token, create_refresh_token
        
        # Create tokens
        access_token = create_access_token({"sub": user_id})
        refresh_token = create_refresh_token({"sub": user_id})
        
        # Create session
        expires_at = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        session = UserSession(
            user_id=user_id,
            access_token=access_token,
            refresh_token=refresh_token,
            user_agent=user_agent,
            ip_address=ip_address,
            expires_at=expires_at
        )
        
        # Save session
        self.sessions[session.id] = session
        self._save_data("sessions")
        
        # Update user's last login
        user = self.get_user_by_id(user_id)
        if user:
            user.last_login = datetime.utcnow()
            self._save_data("users")
        
        return session
    
    def get_session(self, session_id: str) -> Optional[UserSession]:
        """Get a session by ID."""
        return self.sessions.get(session_id)
    
    def get_session_by_token(self, token: str, token_type: str = "access") -> Optional[UserSession]:
        """Get a session by access or refresh token."""
        for session in self.sessions.values():
            if token_type == "access" and session.access_token == token:
                return session
            if token_type == "refresh" and session.refresh_token == token:
                return session
        return None
    
    def revoke_session(self, session_id: str) -> bool:
        """Revoke a session."""
        if session_id in self.sessions:
            del self.sessions[session_id]
            self._save_data("sessions")
            return True
        return False
    
    def revoke_all_sessions(self, user_id: str, exclude_session_id: Optional[str] = None) -> int:
        """Revoke all sessions for a user, optionally excluding one."""
        revoked = 0
        sessions_to_remove = []
        
        for session_id, session in self.sessions.items():
            if session.user_id == user_id and session_id != exclude_session_id:
                sessions_to_remove.append(session_id)
        
        for session_id in sessions_to_remove:
            del self.sessions[session_id]
            revoked += 1
        
        if revoked > 0:
            self._save_data("sessions")
        
        return revoked

# Create a global database instance
db = Database()
