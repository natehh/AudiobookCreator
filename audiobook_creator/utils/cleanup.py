import os
import re
from datetime import datetime, timezone
import logging
from sqlalchemy.orm import Session
from ..core.database import get_db, Conversion
from pathlib import Path

logger = logging.getLogger(__name__)

def cleanup_expired_audiobooks(db: Session):
    """Delete expired audiobooks and update their records."""
    try:
        # Get all expired conversions
        now_utc = datetime.now(timezone.utc)
        expired_conversions = db.query(Conversion).filter(
            Conversion.status == "completed"
        ).all()
        
        # Filter expired conversions manually to handle timezone-naive dates
        expired_conversions = [
            conv for conv in expired_conversions 
            if conv.expiration_date and conv.expiration_date.replace(tzinfo=timezone.utc) < now_utc
        ]

        for conversion in expired_conversions:
            formatted_title = conversion.title.replace(" ", "_")
            formatted_voice_name = re.search(r'-(\w+)Neural$', conversion.voice_id).group(1)
            file_name = f"{formatted_title} ({formatted_voice_name})"
            logger.info(f"File name: {file_name}")
            # Construct the audiobook file path
            file_path = Path("/app/output") / f"{file_name}"
            # Delete the file if it exists
            if file_path.exists():
                try:
                    os.remove(file_path) if file_path.is_file() else os.rmdir(file_path)
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