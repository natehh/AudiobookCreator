import os
import logging
import magic
import hashlib
from fastapi import UploadFile, HTTPException
from pathlib import Path
import re

# Set up logging
logger = logging.getLogger(__name__)

# Define allowed file types and their corresponding MIME types
ALLOWED_MIME_TYPES = {
    '.epub': ['application/epub+zip'],
    '.mobi': ['application/x-mobipocket-ebook', 'application/octet-stream'],
    '.txt': ['text/plain']
}

# Maximum file size (10 MB)
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB in bytes

async def validate_file_upload(file: UploadFile) -> bool:
    """
    Validates an uploaded file for security concerns.
    
    Checks:
    1. File size
    2. File extension
    3. MIME type matches extension
    4. No malicious content patterns
    
    Args:
        file: The uploaded file object
        
    Returns:
        bool: True if file passes all security checks
        
    Raises:
        HTTPException: If any validation fails
    """
    if not file or not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")
    
    # Validate file extension
    file_ext = os.path.splitext(file.filename.lower())[1]
    if file_ext not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=400, 
            detail=f"Unsupported file format. Allowed formats: {', '.join(ALLOWED_MIME_TYPES.keys())}"
        )
    
    # Read the file content for validation
    content = await file.read()
    file_size = len(content)
    
    # Reset file position for future reads
    await file.seek(0)
    
    # Check file size
    if file_size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400, 
            detail=f"File too large. Maximum size: {MAX_FILE_SIZE / (1024 * 1024)}MB"
        )
    
    # Create a temporary file to check mime type
    temp_file = f"temp_validation_{hashlib.md5(file.filename.encode()).hexdigest()}{file_ext}"
    try:
        with open(temp_file, "wb") as f:
            f.write(content)
        
        # Check the actual MIME type using python-magic
        mime_type = magic.from_file(temp_file, mime=True)
        
        # Validate MIME type
        if mime_type not in ALLOWED_MIME_TYPES.get(file_ext, []):
            logger.warning(f"MIME type mismatch: {file.filename} has type {mime_type}")
            raise HTTPException(
                status_code=400, 
                detail=f"File content doesn't match its extension. Got {mime_type}."
            )
        
        # For text files, scan for potentially malicious content
        if file_ext == '.txt':
            with open(temp_file, 'r', errors='ignore') as f:
                text_content = f.read()
                
                # Check for potentially malicious patterns in text files
                suspicious_patterns = [
                    r'<script.*?>.*?</script>',           # JavaScript tags
                    r'<\?php.*?\?>',                      # PHP tags
                    r'eval\s*\(',                         # eval() function
                    r'document\.cookie',                  # Cookie manipulation
                    r'\.\./',                             # Directory traversal
                    r'exec\s*\(',                         # Command execution
                    r'system\s*\('                        # System calls
                ]
                
                for pattern in suspicious_patterns:
                    if re.search(pattern, text_content, re.IGNORECASE | re.DOTALL):
                        logger.warning(f"Suspicious content detected in {file.filename}: {pattern}")
                        raise HTTPException(
                            status_code=400, 
                            detail="File contains potentially malicious content"
                        )
        
        return True
        
    finally:
        # Clean up the temporary file
        if os.path.exists(temp_file):
            os.remove(temp_file)

async def save_validated_file(file: UploadFile, destination_path: str = None) -> str:
    """
    Saves a file that has already been validated to a safe location.
    
    Args:
        file: The validated uploaded file
        destination_path: Optional custom path to save the file
        
    Returns:
        str: The path where the file was saved
    """
    if not destination_path:
        # Generate a safe filename with a UUID to prevent overwriting
        file_ext = os.path.splitext(file.filename.lower())[1]
        safe_filename = f"upload_{hashlib.md5(file.filename.encode()).hexdigest()}{file_ext}"
        destination_path = os.path.join("tmp", safe_filename)
    
    # Create directory if it doesn't exist and needed
    dir_name = os.path.dirname(destination_path)
    if dir_name:  # Only try to create directory if there's a directory component
        os.makedirs(dir_name, exist_ok=True)
    
    # Save the file
    content = await file.read()
    with open(destination_path, "wb") as f:
        f.write(content)
    
    # Reset file position
    await file.seek(0)
    
    return destination_path 