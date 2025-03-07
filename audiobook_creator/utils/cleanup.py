import os
import re
from datetime import datetime, timezone
import logging
from sqlalchemy.orm import Session
from ..core.database import get_db, Conversion
from pathlib import Path

logger = logging.getLogger(__name__)

def sanitize_path(input_str):
    """
    Sanitize a string to be safely used as a file path component.
    
    Args:
        input_str: String to sanitize
        
    Returns:
        Sanitized string safe for file path usage
    """
    if not input_str:
        return "untitled"
        
    # Extract only the basename (no directory components)
    safe_name = os.path.basename(input_str)
    
    # Allow only alphanumeric chars, spaces, and certain punctuation
    safe_name = re.sub(r'[^\w\s\-\.]', '', safe_name)
    
    # Replace spaces with underscores
    safe_name = safe_name.replace(" ", "_")
    
    # Ensure there are no directory traversal patterns
    safe_name = safe_name.replace("..", "")
    
    # Limit length to a reasonable size
    safe_name = safe_name[:100]
    
    return safe_name if safe_name else "untitled"

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
            # Sanitize the title before constructing the file path
            formatted_title = sanitize_path(conversion.title)
            
            # Sanitize voice name extraction
            voice_name_match = re.search(r'-(\w+)Neural$', conversion.voice_id)
            formatted_voice_name = voice_name_match.group(1) if voice_name_match else "Voice"
            formatted_voice_name = sanitize_path(formatted_voice_name)
            
            file_name = f"{formatted_title} ({formatted_voice_name})"
            logger.info(f"File name: {file_name}")
            
            # Construct the audiobook file path using os.path.join for safety
            output_dir = Path("/app/output")
            file_path = output_dir / file_name
            
            # Validate that the file_path is actually within the output directory
            # This prevents path traversal attacks
            try:
                # Use resolve() to get the absolute normalized path
                real_path = file_path.resolve()
                output_dir_resolved = output_dir.resolve()
                
                # Ensure the resolved path is within the output directory
                if output_dir_resolved in real_path.parents:
                    # Delete the file if it exists
                    if real_path.exists():
                        try:
                            if real_path.is_file():
                                os.remove(real_path)
                            elif real_path.is_dir():
                                os.rmdir(real_path)
                            logger.info(f"Deleted expired audiobook: {real_path}")
                        except OSError as e:
                            logger.error(f"Error deleting audiobook {real_path}: {e}")
                else:
                    logger.error(f"Security check failed: {file_path} resolves outside output directory")
            except (ValueError, RuntimeError) as e:
                logger.error(f"Security error while resolving path: {e}")
            
            # Update the conversion status
            conversion.status = "expired"
            
        db.commit()
        logger.info(f"Cleaned up {len(expired_conversions)} expired audiobooks")
    except Exception as e:
        logger.error(f"Error during audiobook cleanup: {e}")
        db.rollback() 