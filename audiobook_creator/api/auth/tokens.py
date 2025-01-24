import secrets

def generate_access_token(user_id: int) -> str:
    """Generate a dummy access token."""
    return secrets.token_hex(32)
