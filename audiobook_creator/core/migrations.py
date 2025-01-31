from sqlalchemy import create_engine, text, MetaData
from sqlalchemy.engine import Engine
import logging
from .database import Base

logger = logging.getLogger(__name__)

def ensure_tables_exist(engine: Engine):
    """Drop all tables and recreate them."""
    # Drop all tables
    Base.metadata.drop_all(bind=engine)
    logger.info("Dropped all existing tables")
    
    # Create all tables with new schema
    Base.metadata.create_all(bind=engine)
    logger.info("Created all tables with new schema")

def run_migrations(database_url: str):
    engine = create_engine(database_url)
    
    try:
        # Recreate all tables with new schema
        ensure_tables_exist(engine)
        logger.info("Database migration completed successfully")
    except Exception as e:
        logger.error(f"Error running migrations: {str(e)}")
        raise