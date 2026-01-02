from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from pydantic import BaseModel, EmailStr, Field, validator
import uuid

class UserBase(BaseModel):
    """Base user model with common fields."""
    username: str
    email: EmailStr
    full_name: Optional[str] = None
    disabled: bool = False
    is_verified: bool = False
    
    class Config:
        orm_mode = True

class UserCreate(UserBase):
    """Model for creating a new user."""
    password: str
    
    @validator('password')
    def password_must_be_strong(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        # Add more password strength validations as needed
        return v

class UserInDB(UserBase):
    """User model as stored in the database."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    hashed_password: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    last_login: Optional[datetime] = None
    
    def verify_password(self, password: str) -> bool:
        """Verify a password against the stored hash."""
        from .config import verify_password
        return verify_password(password, self.hashed_password)

class Token(BaseModel):
    """Authentication token model."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    refresh_token: Optional[str] = None
    user_id: str

class TokenData(BaseModel):
    """Token payload model."""
    user_id: Optional[str] = None
    username: Optional[str] = None
    type: Optional[str] = None

class OTP(BaseModel):
    """OTP (One-Time Password) model."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    email: EmailStr
    otp: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: datetime
    is_used: bool = False
    
    @classmethod
    def create_new(cls, email: str, otp: str, expires_in_minutes: int = 5):
        """Create a new OTP instance."""
        return cls(
            email=email,
            otp=otp,
            expires_at=datetime.utcnow() + timedelta(minutes=expires_in_minutes)
        )
    
    def is_expired(self) -> bool:
        """Check if the OTP has expired."""
        return datetime.utcnow() > self.expires_at
    
    def verify(self, otp: str) -> bool:
        """Verify the OTP."""
        if self.is_expired():
            return False
        if self.is_used:
            return False
        return self.otp == otp

class UserSession(BaseModel):
    """User session model."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    access_token: str
    refresh_token: str
    user_agent: Optional[str] = None
    ip_address: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: datetime
    is_active: bool = True
    
    def is_expired(self) -> bool:
        """Check if the session has expired."""
        return datetime.utcnow() > self.expires_at
    
    def to_token_response(self) -> Dict[str, Any]:
        """Convert session to token response."""
        return {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "token_type": "bearer",
            "expires_in": int((self.expires_at - datetime.utcnow()).total_seconds())
        }
