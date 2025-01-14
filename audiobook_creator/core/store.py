from typing import Dict, Optional
from ..api.models import ConversionStatus

class ConversionStore:
    """Store for managing conversion status updates."""
    def __init__(self):
        self.conversions: Dict[str, ConversionStatus] = {}
    
    def add(self, status: ConversionStatus):
        """Add a new conversion status."""
        self.conversions[status.id] = status
    
    def get(self, conversion_id: str) -> Optional[ConversionStatus]:
        """Get status of a specific conversion."""
        return self.conversions.get(conversion_id)
    
    def update(self, conversion_id: str, **kwargs):
        """Update status of a specific conversion."""
        if conversion_id in self.conversions:
            current = self.conversions[conversion_id].model_dump()
            current.update(kwargs)
            self.conversions[conversion_id] = ConversionStatus(**current)