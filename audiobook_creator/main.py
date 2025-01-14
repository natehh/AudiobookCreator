from .api.routes import AudiobookAPI

api = AudiobookAPI()
app = api.app