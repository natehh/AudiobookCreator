import os
from datetime import datetime
import logging
from sqlalchemy.orm import Session
from ..core.database import get_db, Conversion
from pathlib import Path

logger = logging.getLogger(__name__)

def cleanup_expired_audiobooks(db: Session):
    """Delete expired audiobooks and update their records."""
    try:
        # Get all expired conversions
        expired_conversions = db.query(Conversion).filter(
            Conversion.expiration_date < datetime.utcnow(),
            Conversion.status == "completed"
        ).all()

        for conversion in expired_conversions:
            # Construct the audiobook file path
            file_path = Path("/app/data/audiobooks") / f"{conversion.id}.m4b"
            
            # Delete the file if it exists
            if file_path.exists():
                try:
                    os.remove(file_path)
                    logger.info(f"Deleted expired audiobook: {file_path}")
                except OSError as e:
                    logger.error(f"Error deleting audiobook {file_path}: {e}")
            
            # Update the conversion status
            conversion.status = "expired"
            
        db.commit()
        logger.info(f"Cleaned up {len(expired_conversions)} expired audiobooks")
    except Exception as e:
        logger.error(f"Error during audiobook cleanup: {e}")
        db.rollback() 