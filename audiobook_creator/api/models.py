from typing import List, Optional, Dict
from pydantic import BaseModel

class ConversionStatus(BaseModel):
    """Model representing the status of an audiobook conversion."""
    id: str
    status: str
    progress: float
    eta: Optional[str] = None
    output_files: List[str] = []
    error: Optional[str] = None
    temp_file: Optional[str] = None
    # Additional fields for complete status
    title: Optional[str] = None
    author: Optional[str] = None
    voice: Optional[str] = None
    created_at: Optional[str] = None
    expiration_date: Optional[str] = None