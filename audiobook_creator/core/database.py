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
    source = Column(String, nullable=False)
    tier_id = Column(Integer, ForeignKey("voice_tiers.id"), nullable=False)
    usage_count = Column(BigInteger, default=0)
    language = Column(String, nullable=False)
    gender = Column(String)  # Male/Female/Neutral
    description = Column(String)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    tier_info = relationship("VoiceTier", back_populates="voices")

class VoiceTier(Base):
    __tablename__ = "voice_tiers"
    
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False, unique=True)  # e.g., "Basic", "Premium", "Enterprise"
    price_per_char = Column(Float, nullable=False)
    description = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    voices = relationship("VoicePricing", back_populates="tier_info")

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

def populate_initial_tiers(db: Session):
    """Populate initial voice tiers if they don't exist."""
    try:
        # Define initial tiers
        initial_tiers = [
            {
                "name": "Basic",
                "price_per_char": 0.000015,
                "description": "High-quality voices for personal projects"
            },
            {
                "name": "Premium",
                "price_per_char": 0.000025,
                "description": "Professional voices with enhanced clarity and natural intonation"
            },
            {
                "name": "Enterprise",
                "price_per_char": 0.000040,
                "description": "Studio-quality voices with the highest fidelity and expression"
            }
        ]
        
        # Add tiers if they don't exist
        for tier_data in initial_tiers:
            existing_tier = db.query(VoiceTier).filter_by(name=tier_data["name"]).first()
            if not existing_tier:
                tier = VoiceTier(**tier_data)
                db.add(tier)
        
        db.commit()
        logger.info("Initial tiers populated successfully")
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error populating initial tiers: {str(e)}")
        raise

def populate_initial_voices(db: Session):
    """Populate initial voices if they don't exist."""
    try:
        # Get tier IDs
        tiers = {tier.name: tier.id for tier in db.query(VoiceTier).all()}
        
        # Define initial voices
        initial_voices = [
            {
                "name": "Emma",
                "country": "US",
                "language": "English",
                "source": "azure",
                "tier_id": tiers["Premium"],
                "gender": "Female",
                "description": "Warm and professional American accent"
            },
            {
                "name": "James",
                "country": "UK",
                "language": "English",
                "source": "azure",
                "tier_id": tiers["Premium"],
                "gender": "Male",
                "description": "Clear British accent"
            },
            {
                "name": "Sarah",
                "country": "Australia",
                "language": "English",
                "source": "azure",
                "tier_id": tiers["Basic"],
                "gender": "Female",
                "description": "Friendly Australian accent"
            },
            {
                "name": "Michael",
                "country": "Canada",
                "language": "English",
                "source": "azure",
                "tier_id": tiers["Enterprise"],
                "gender": "Male",
                "description": "Professional Canadian accent"
            }
        ]
        
        # Add voices if they don't exist
        for voice_data in initial_voices:
            existing_voice = db.query(VoicePricing).filter_by(name=voice_data["name"]).first()
            if not existing_voice:
                voice = VoicePricing(**voice_data)
                db.add(voice)
        
        db.commit()
        logger.info("Initial voices populated successfully")
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error populating initial voices: {str(e)}")
        raise

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
    
    # Initialize session and populate tiers and voices
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    try:
        populate_initial_tiers(db)
        populate_initial_voices(db)
    finally:
        db.close()
    
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