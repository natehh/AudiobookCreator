import time
from typing import Dict, Tuple, List, Optional
from fastapi import Request, HTTPException, Depends
import logging
from datetime import datetime, timedelta
import threading

logger = logging.getLogger(__name__)

# Simple in-memory storage for rate limiting
# In production, this should use Redis or another distributed cache
class RateLimitStorage:
    def __init__(self):
        self.requests: Dict[str, List[float]] = {}
        self.blocked_ips: Dict[str, float] = {}
        # Mutex for thread safety
        self.lock = threading.Lock()
        
    def add_request(self, key: str, timestamp: float = None):
        """Record a request for a specific key (IP or user ID)."""
        if timestamp is None:
            timestamp = time.time()
            
        with self.lock:
            if key not in self.requests:
                self.requests[key] = []
            self.requests[key].append(timestamp)
    
    def clean_old_requests(self, key: str, window: float):
        """Remove requests older than the time window."""
        if key not in self.requests:
            return
            
        current_time = time.time()
        with self.lock:
            self.requests[key] = [
                ts for ts in self.requests[key] 
                if current_time - ts < window
            ]
    
    def get_request_count(self, key: str, window: float) -> int:
        """Get number of requests within the time window."""
        self.clean_old_requests(key, window)
        
        with self.lock:
            return len(self.requests.get(key, []))
    
    def is_rate_limited(self, key: str, max_requests: int, window: float) -> bool:
        """Check if a key has exceeded rate limits."""
        # First check if the IP is blocked
        with self.lock:
            if key in self.blocked_ips:
                if time.time() - self.blocked_ips[key] > window * 5:  # Block for 5x the window time
                    del self.blocked_ips[key]
                else:
                    return True
        
        # Check rate limits
        count = self.get_request_count(key, window)
        if count >= max_requests:
            # If consistently exceeding the limit, block the IP
            if count >= max_requests * 2:
                with self.lock:
                    self.blocked_ips[key] = time.time()
                logger.warning(f"IP {key} has been blocked for excessive requests")
            return True
        return False
    
    def get_retry_after(self, key: str, window: float) -> int:
        """Calculate how long until rate limit resets."""
        if key not in self.requests or not self.requests[key]:
            return 0
            
        with self.lock:
            oldest_timestamp = min(self.requests[key])
            current_time = time.time()
            
            # When the oldest request will expire
            reset_time = oldest_timestamp + window - current_time
            return max(1, int(reset_time))

# Global rate limit storage
RATE_LIMITER = RateLimitStorage()

# Rate limit dependency factory
def rate_limit(
    max_requests: int = 10,
    window: float = 60,  # in seconds
    by_ip: bool = True,
):
    """
    Rate limiting dependency.
    
    Args:
        max_requests: Maximum number of requests allowed in the time window
        window: Time window in seconds
        by_ip: Whether to rate limit by IP address (if False, uses user ID if available)
    """
    async def rate_limit_dependency(request: Request):
        # Determine the key to use for rate limiting
        if by_ip:
            key = request.client.host
        else:
            # Can be extended to use user ID if authenticated
            key = request.client.host
        
        # Add the request to the storage
        RATE_LIMITER.add_request(key)
        
        # Check if rate limited
        if RATE_LIMITER.is_rate_limited(key, max_requests, window):
            retry_after = RATE_LIMITER.get_retry_after(key, window)
            
            # Log the rate-limiting event
            logger.warning(f"Rate limit exceeded for {key}. Retry after {retry_after} seconds.")
            
            # Create a proper 429 response with headers
            headers = {
                "Retry-After": str(retry_after),
                "X-RateLimit-Limit": str(max_requests),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(int(time.time() + retry_after))
            }
            
            raise HTTPException(
                status_code=429, 
                detail="Too many requests. Please try again later.",
                headers=headers
            )
        
        return True
    
    return rate_limit_dependency

# Commonly used rate limiters
auth_rate_limit = rate_limit(max_requests=5, window=60)  # 5 requests per minute for auth endpoints
conversion_rate_limit = rate_limit(max_requests=3, window=300)  # 3 requests per 5 minutes for conversions
general_rate_limit = rate_limit(max_requests=60, window=60)  # 60 requests per minute for general endpoints 