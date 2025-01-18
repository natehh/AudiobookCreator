from typing import Dict, Optional
from ..api.models import ConversionStatus
import asyncio

class ConversionStore:
    """Store for managing conversion status updates."""
    def __init__(self, app=None):
        self.conversions: Dict[str, ConversionStatus] = {}
        self.app = app

    async def broadcast_update(self, conversion_id: str, status: ConversionStatus):
        if self.app and hasattr(self.app, 'active_connections'):
            for cid, websocket in self.app.active_connections:
                if cid == conversion_id:
                    try:
                        await websocket.send_json(status.dict())
                    except:
                        continue
    
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