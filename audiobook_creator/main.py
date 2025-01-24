from .api.routes import AudiobookAPI
from .api.auth.routes import auth_router

api = AudiobookAPI()
app = api.app
app.include_router(auth_router, prefix="/auth", tags=["auth"])