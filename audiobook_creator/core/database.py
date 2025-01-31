from sqlalchemy import create_engine, Column, Integer, String, Float, ForeignKey, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, Session
import logging
from datetime import datetime

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

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def initialize_db():
    logger.info("Creating database and tables...")
    Base.metadata.create_all(bind=engine)
    logger.info("Database and tables created.")

def init_db(engine):
    Base.metadata.create_all(bind=engine)