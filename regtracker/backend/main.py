from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, String, Boolean, DateTime, Text, Float, JSON, Enum as SQLEnum, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship
from pydantic import BaseModel, EmailStr
from datetime import datetime, timedelta
from typing import Optional, List
import jwt
import bcrypt
import os
from uuid import uuid4
import enum

# Configuration
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@localhost/regtracker")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# Database setup
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Enums
class NotificationFrequency(str, enum.Enum):
    daily = "daily"
    weekly = "weekly"
    monthly = "monthly"

class DocumentType(str, enum.Enum):
    legislation = "legislation"
    amendment = "amendment"
    guidance = "guidance"

# Database Models
class User(Base):
    __tablename__ = "users"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    email = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    full_name = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    
    preferences = relationship("UserPreference", back_populates="user", uselist=False)
    reports = relationship("UserReport", back_populates="user")

class UserPreference(Base):
    __tablename__ = "user_preferences"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    jurisdiction = Column(String, default="EU")
    sectors = Column(JSON, default=list)
    notification_frequency = Column(SQLEnum(NotificationFrequency), default=NotificationFrequency.weekly)
    email_notifications = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User", back_populates="preferences")

class RegulatoryChange(Base):
    __tablename__ = "regulatory_changes"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    title = Column(String, nullable=False)
    jurisdiction = Column(String, nullable=False)
    document_type = Column(SQLEnum(DocumentType), nullable=False)
    publication_date = Column(DateTime, nullable=False)
    source_url = Column(String, nullable=False)
    source_name = Column(String, default="EUR-Lex")
    cellar_id = Column(String, unique=True, nullable=False, index=True)
    raw_text = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    reports = relationship("UserReport", back_populates="regulatory_change")

class UserReport(Base):
    __tablename__ = "user_reports"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    regulatory_change_id = Column(String, ForeignKey("regulatory_changes.id"), nullable=False)
    summary = Column(Text)
    relevance_explanation = Column(Text)
    key_impacts = Column(JSON, default=list)
    relevance_score = Column(Float)
    is_read = Column(Boolean, default=False)
    is_starred = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User", back_populates="reports")
    regulatory_change = relationship("RegulatoryChange", back_populates="reports")

# Create tables
Base.metadata.create_all(bind=engine)

# Pydantic Models
class UserRegister(BaseModel):
    email: EmailStr
    password: str
    full_name: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserPreferenceUpdate(BaseModel):
    jurisdiction: Optional[str] = None
    sectors: Optional[List[str]] = None
    notification_frequency: Optional[NotificationFrequency] = None
    email_notifications: Optional[bool] = None

class ReportUpdate(BaseModel):
    is_read: Optional[bool] = None
    is_starred: Optional[bool] = None

class TokenResponse(BaseModel):
    access_token: str
    token_type: str

class UserResponse(BaseModel):
    id: str
    email: str
    full_name: str
    created_at: datetime

class PreferenceResponse(BaseModel):
    jurisdiction: str
    sectors: List[str]
    notification_frequency: str
    email_notifications: bool

class ReportResponse(BaseModel):
    id: str
    title: str
    jurisdiction: str
    document_type: str
    publication_date: datetime
    source_url: str
    summary: Optional[List[str]]
    relevance_explanation: Optional[str]
    key_impacts: List[str]
    relevance_score: Optional[float]
    is_read: bool
    is_starred: bool
    created_at: datetime

# FastAPI app
app = FastAPI(title="Regulatory Changes Tracker API")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

security = HTTPBearer()

# Database dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Auth helpers
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())

def create_token(user_id: str) -> str:
    payload = {
        "user_id": user_id,
        "exp": datetime.utcnow() + timedelta(days=7)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=["HS256"])
        return payload["user_id"]
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

# Routes
@app.get("/")
def root():
    return {
        "service": "Regulatory Changes Tracker API",
        "version": "1.0.0",
        "status": "operational"
    }

@app.post("/api/auth/register", response_model=TokenResponse)
def register(user_data: UserRegister, db: Session = Depends(get_db)):
    # Check if user exists
    existing = db.query(User).filter(User.email == user_data.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Create user
    user = User(
        id=str(uuid4()),
        email=user_data.email,
        password_hash=hash_password(user_data.password),
        full_name=user_data.full_name
    )
    db.add(user)
    
    # Create default preferences
    preferences = UserPreference(
        id=str(uuid4()),
        user_id=user.id,
        jurisdiction="EU",
        sectors=["IT", "Finance"]
    )
    db.add(preferences)
    db.commit()
    
    token = create_token(user.id)
    return {"access_token": token, "token_type": "bearer"}

@app.post("/api/auth/login", response_model=TokenResponse)
def login(credentials: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == credentials.email).first()
    if not user or not verify_password(credentials.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    token = create_token(user.id)
    return {"access_token": token, "token_type": "bearer"}

@app.get("/api/user/me", response_model=UserResponse)
def get_current_user(user_id: str = Depends(verify_token), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@app.get("/api/user/preferences", response_model=PreferenceResponse)
def get_preferences(user_id: str = Depends(verify_token), db: Session = Depends(get_db)):
    prefs = db.query(UserPreference).filter(UserPreference.user_id == user_id).first()
    if not prefs:
        raise HTTPException(status_code=404, detail="Preferences not found")
    return prefs

@app.put("/api/user/preferences", response_model=PreferenceResponse)
def update_preferences(
    updates: UserPreferenceUpdate,
    user_id: str = Depends(verify_token),
    db: Session = Depends(get_db)
):
    prefs = db.query(UserPreference).filter(UserPreference.user_id == user_id).first()
    if not prefs:
        raise HTTPException(status_code=404, detail="Preferences not found")
    
    if updates.jurisdiction is not None:
        prefs.jurisdiction = updates.jurisdiction
    if updates.sectors is not None:
        prefs.sectors = updates.sectors
    if updates.notification_frequency is not None:
        prefs.notification_frequency = updates.notification_frequency
    if updates.email_notifications is not None:
        prefs.email_notifications = updates.email_notifications
    
    db.commit()
    db.refresh(prefs)
    return prefs

@app.get("/api/reports", response_model=List[ReportResponse])
def get_reports(
    skip: int = 0,
    limit: int = 20,
    starred_only: bool = False,
    unread_only: bool = False,
    user_id: str = Depends(verify_token),
    db: Session = Depends(get_db)
):
    query = db.query(UserReport).filter(UserReport.user_id == user_id)
    
    if starred_only:
        query = query.filter(UserReport.is_starred == True)
    if unread_only:
        query = query.filter(UserReport.is_read == False)
    
    reports = query.order_by(UserReport.created_at.desc()).offset(skip).limit(limit).all()
    
    result = []
    for report in reports:
        reg_change = report.regulatory_change
        result.append({
            "id": report.id,
            "title": reg_change.title,
            "jurisdiction": reg_change.jurisdiction,
            "document_type": reg_change.document_type.value,
            "publication_date": reg_change.publication_date,
            "source_url": reg_change.source_url,
            "summary": report.summary if isinstance(report.summary, list) else [],
            "relevance_explanation": report.relevance_explanation,
            "key_impacts": report.key_impacts or [],
            "relevance_score": report.relevance_score,
            "is_read": report.is_read,
            "is_starred": report.is_starred,
            "created_at": report.created_at
        })
    
    return result

@app.get("/api/reports/{report_id}", response_model=ReportResponse)
def get_report(
    report_id: str,
    user_id: str = Depends(verify_token),
    db: Session = Depends(get_db)
):
    report = db.query(UserReport).filter(
        UserReport.id == report_id,
        UserReport.user_id == user_id
    ).first()
    
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    
    reg_change = report.regulatory_change
    return {
        "id": report.id,
        "title": reg_change.title,
        "jurisdiction": reg_change.jurisdiction,
        "document_type": reg_change.document_type.value,
        "publication_date": reg_change.publication_date,
        "source_url": reg_change.source_url,
        "summary": report.summary if isinstance(report.summary, list) else [],
        "relevance_explanation": report.relevance_explanation,
        "key_impacts": report.key_impacts or [],
        "relevance_score": report.relevance_score,
        "is_read": report.is_read,
        "is_starred": report.is_starred,
        "created_at": report.created_at
    }

@app.patch("/api/reports/{report_id}", response_model=ReportResponse)
def update_report(
    report_id: str,
    updates: ReportUpdate,
    user_id: str = Depends(verify_token),
    db: Session = Depends(get_db)
):
    report = db.query(UserReport).filter(
        UserReport.id == report_id,
        UserReport.user_id == user_id
    ).first()
    
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    
    if updates.is_read is not None:
        report.is_read = updates.is_read
    if updates.is_starred is not None:
        report.is_starred = updates.is_starred
    
    db.commit()
    db.refresh(report)
    
    reg_change = report.regulatory_change
    return {
        "id": report.id,
        "title": reg_change.title,
        "jurisdiction": reg_change.jurisdiction,
        "document_type": reg_change.document_type.value,
        "publication_date": reg_change.publication_date,
        "source_url": reg_change.source_url,
        "summary": report.summary if isinstance(report.summary, list) else [],
        "relevance_explanation": report.relevance_explanation,
        "key_impacts": report.key_impacts or [],
        "relevance_score": report.relevance_score,
        "is_read": report.is_read,
        "is_starred": report.is_starred,
        "created_at": report.created_at
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)