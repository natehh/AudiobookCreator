from sqlalchemy import create_engine, Column, Integer, String, Float, ForeignKey, DateTime, Enum, BigInteger, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, Session
import logging
from datetime import datetime
import os
from sqlalchemy.sql import text
import yaml
from pathlib import Path

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
    stripe_customer_id = Column(String, unique=True, nullable=True)
    payments = relationship("Payment", back_populates="user")
    usages = relationship("Usage", back_populates="user")

class Conversion(Base):
    __tablename__ = "conversions"
    id = Column(String, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    title = Column(String)
    author = Column(String)
    input_size = Column(Integer)
    status = Column(String)
    progress = Column(Float)
    voice_id = Column(String)
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
    voice_id = Column(String, nullable=False)

class VoiceTier(Base):
    __tablename__ = "voice_tiers"
    
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False, unique=True)  # e.g., "Basic", "Premium", "Enterprise"
    price_per_char = Column(Float, nullable=False)
    description = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    voices = relationship("VoicePricing", back_populates="tier_info")

class Payment(Base):
    __tablename__ = "payments"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    amount = Column(Float, nullable=False)
    stripe_payment_intent_id = Column(String, unique=True)
    status = Column(String, nullable=False)  # succeeded, pending, failed
    created_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User", back_populates="payments")

class Usage(Base):
    __tablename__ = "usages"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    characters_processed = Column(Integer, nullable=False)
    amount_charged = Column(Float, nullable=False)
    payment_id = Column(Integer, ForeignKey("payments.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User", back_populates="usages")
    payment = relationship("Payment")

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

def load_voice_config():
    """Load voice configuration from YAML file."""
    config_path = Path(__file__).parent.parent / "config" / "voices.yaml"
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)

def populate_initial_tiers(db: Session):
    """Populate initial voice tiers if they don't exist."""
    try:
        config = load_voice_config()
        
        # Add tiers if they don't exist
        for tier_id, tier_data in config['tiers'].items():
            existing_tier = db.query(VoiceTier).filter_by(name=tier_data["name"]).first()
            if not existing_tier:
                tier = VoiceTier(
                    name=tier_data["name"],
                    price_per_char=tier_data["price_per_char"],
                    description=tier_data["description"],
                )
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
        config = load_voice_config()
        
        # Get tier IDs
        tiers = {tier.name: tier.id for tier in db.query(VoiceTier).all()}
        
        # Add voices from config
        for tier_id, tier_data in config['tiers'].items():
            for voice_data in tier_data['voices']:
                existing_voice = db.query(VoicePricing).filter_by(name=voice_data["name"]).first()
                if not existing_voice:
                    voice = VoicePricing(
                        **voice_data,
                        tier_id=tiers[tier_data["name"]]
                    )
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
    return engine

# Initialize engine once at module level
engine = initialize_db()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    """Get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Populate initial data if needed (run this once when application starts)
def populate_initial_data():
    db = SessionLocal()
    try:
        populate_initial_tiers(db)
        populate_initial_voices(db)
    finally:
        db.close()