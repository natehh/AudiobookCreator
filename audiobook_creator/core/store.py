from typing import Dict, Optional
from ..api.models import ConversionStatus
import asyncio
from sqlalchemy.orm import Session
from ..core.database import get_db, Conversion

class ConversionStore:
    """Store for managing conversion status updates."""
    def __init__(self, app=None):
        self.conversions: Dict[str, ConversionStatus] = {}
        self.app = app

    async def broadcast_update(self, conversion_id: str, status: ConversionStatus):
        if self.app and hasattr(self.app, 'active_connections'):
            # Get database session
            db = next(get_db())
            try:
                # Get conversion details from database
                conversion = db.query(Conversion).filter(Conversion.id == conversion_id).first()
                if conversion:
                    # Update status with additional fields
                    status_dict = status.dict()
                    status_dict.update({
                        'title': conversion.title,
                        'author': conversion.author,
                        'voice': conversion.voice_id,
                        'created_at': conversion.created_at.isoformat() + "Z" if conversion.created_at else None,
                        'expiration_date': conversion.expiration_date.isoformat() + "Z" if conversion.expiration_date else None
                    })
                    # Broadcast to all connected clients for this conversion
                    for cid, websocket in self.app.active_connections:
                        if cid == conversion_id:
                            try:
                                await websocket.send_json(status_dict)
                            except:
                                continue
            finally:
                db.close()
    
    def add(self, status: ConversionStatus):
        """Add a new conversion status."""
        self.conversions[status.id] = status
    
    def get(self, conversion_id: str) -> Optional[ConversionStatus]:
        """Get status of a specific conversion."""
        return self.conversions.get(conversion_id)
    
    def update(self, conversion_id: str, **kwargs):
        """Update status of a specific conversion."""
        status = self.conversions.get(conversion_id)
        if status:
            for key, value in kwargs.items():
                setattr(status, key, value)
            asyncio.create_task(self.broadcast_update(conversion_id, status))