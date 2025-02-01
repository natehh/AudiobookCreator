from sqlalchemy import create_engine, Column, Integer, String, Float, ForeignKey, DateTime, Enum, BigInteger, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, Session
import logging
from datetime import datetime
import os
from sqlalchemy.sql import text

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SQLALCHEMY_DATABASE_URL = "sqlite:////app/data/audiobookcreator.db"

engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True, nullable=False)
    name = Column(String)
    oauth_provider = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    conversions = relationship("Conversion", back_populates="user")

class Conversion(Base):
    __tablename__ = "conversions"
    id = Column(String, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    title = Column(String)
    author = Column(String)
    input_size = Column(Integer)
    status = Column(String)
    progress = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)
    user = relationship("User", back_populates="conversions")

class VoicePricing(Base):
    __tablename__ = "voice_pricing"
    
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    country = Column(String, nullable=False)
    source = Column(String, nullable=False, default='edge')
    price_per_char = Column(Float, nullable=False)
    usage_count = Column(BigInteger, default=0)
    language = Column(String, nullable=False)
    gender = Column(String)  # Male/Female/Neutral
    description = Column(String)
    is_neural = Column(Boolean, default=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

def get_or_create_user(db: Session, user_info: dict) -> User:
    """Get existing user or create a new one."""
    user = db.query(User).filter(User.email == user_info["email"]).first()
    
    if not user:
        user = User(
            email=user_info["email"],
            name=user_info.get("name"),
            oauth_provider="google"
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    
    return user

def initialize_db():
    """Initialize database connection and create tables if they don't exist."""
    database_url = os.getenv("SQLALCHEMY_DATABASE_URL", "sqlite:///audiobookcreator.db")
    engine = create_engine(database_url)

    # Set SQLite pragmas for better performance
    if database_url.startswith('sqlite'):
        with engine.connect() as conn:
            conn.execute(text('PRAGMA foreign_keys = ON;'))
            conn.execute(text('PRAGMA journal_mode = WAL;'))
            conn.commit()

    # Create all tables
    Base.metadata.create_all(bind=engine)
    
    return engine

def get_db():
    """Get database session."""
    engine = initialize_db()
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()