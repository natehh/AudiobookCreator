from sqlalchemy import create_engine, Column, Integer, String, Float, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SQLALCHEMY_DATABASE_URL = "sqlite:////app/data/audiobookcreator.db"

engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    oauth_provider = Column(String)
    provider_id = Column(String)
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
    user = relationship("User", back_populates="conversions")

def get_or_create_user(db, user_info):
    """Get user by email or create a new one."""
    user = db.query(User).filter(User.email == user_info["email"]).first()
    if not user:
        user = User(
            email=user_info["email"],
            oauth_provider=user_info["oauth_provider"],
            provider_id=user_info["id"]
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