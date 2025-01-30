import os
import uuid
from fastapi import FastAPI, UploadFile, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi import WebSocket
from pathlib import Path
from ..core.converter import AudiobookConverter
from ..core.store import ConversionStore
from .models import ConversionStatus
from fastapi import Depends
from sqlalchemy.orm import Session
from ..core.database import get_db, Conversion, get_or_create_user
from ..utils.ebook import get_book_metadata
from .auth.tokens import JWTBearer, JWTHandler
import re
import logging

logger = logging.getLogger(__name__)

class AudiobookAPI:
    """FastAPI application for audiobook conversion."""
    def __init__(self):
        self.app = FastAPI()
        self.store = ConversionStore(self)
        self.active_connections = []
        self._setup_middleware()
        self._setup_static_files()
        self.setup_routes()
    
    def _setup_middleware(self):
        """Configure CORS middleware."""
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    def _setup_static_files(self):
        """Configure static file serving."""
        static_dir = Path(__file__).parent.parent / "static"
        static_dir.mkdir(exist_ok=True)
        self.app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
    
    def setup_routes(self):
        """Configure API routes."""
        @self.app.websocket("/ws/{conversion_id}")
        async def websocket_endpoint(websocket: WebSocket, conversion_id: str):
            await websocket.accept()
            self.active_connections.append((conversion_id, websocket))
            try:
                while True:
                    await websocket.receive_text()  # Keep connection alive
            except:
                self.active_connections.remove((conversion_id, websocket))

        @self.app.get("/")
        async def read_root():
            """Serve the main HTML page."""
            static_dir = Path(__file__).parent.parent / "static"
            return FileResponse(static_dir / "index.html")
        
        @self.app.post("/convert/", response_model=ConversionStatus)
        async def create_conversion(
            background_tasks: BackgroundTasks,
            file: UploadFile,
            token: str = Depends(JWTBearer()),
            output_dir: str = "output",
            db: Session = Depends(get_db)
        ):
            if not file.filename.endswith(('.epub', '.mobi', '.txt')):
                raise HTTPException(400, "Unsupported file format")
            
            temp_path = f"temp_{uuid.uuid4()}{os.path.splitext(file.filename)[1]}"
            with open(temp_path, "wb") as f:
                f.write(await file.read())
            
            converter = AudiobookConverter(temp_path, output_dir, self.store)
            
            status = ConversionStatus(
                id=converter.conversion_id,
                status="processing",
                progress=0.0,
                temp_file=temp_path
            )
            self.store.add(status)

            # Get user email from token
            user_email = JWTHandler.verify_token(token)
            
            # Get or create the user
            user_info = {"email": user_email}
            user = get_or_create_user(db, user_info)
            
            # Get book metadata
            book_metadata = get_book_metadata(Path(temp_path))
            
            # Create a new conversion record
            conversion = Conversion(
                id=converter.conversion_id,
                user_id=user.id,
                title=book_metadata["title"],
                author=book_metadata["author"],
                input_size=os.path.getsize(temp_path),
                status="processing",
                progress=0.0
            )
            db.add(conversion)
            db.commit()
            db.refresh(conversion)
            
            background_tasks.add_task(converter.convert)
            
            return status
        
        @self.app.get("/conversion/{conversion_id}")
        async def conversion_page(conversion_id: str):
            """Serve the conversion-specific page."""
            static_dir = Path(__file__).parent.parent / "static"
            return FileResponse(static_dir / "conversion.html")


        @self.app.get("/status/{conversion_id}", response_model=ConversionStatus)
        async def get_status(conversion_id: str):
            status = self.store.get(conversion_id)
            if not status:
                raise HTTPException(404, "Conversion not found")
            return status

        @self.app.delete("/cleanup/{conversion_id}")
        async def cleanup_conversion(conversion_id: str):
            status = self.store.get(conversion_id)
            if not status:
                raise HTTPException(404, "Conversion not found")
            
            if status.temp_file and os.path.exists(status.temp_file):
                os.remove(status.temp_file)
            
            return {"message": "Cleanup completed"}
        
        @self.app.get("/download/{conversion_id}")
        async def download_audiobook(conversion_id: str):
            status = self.store.get(conversion_id)
            if not status:
                raise HTTPException(404, "Conversion not found")
            if status.status != "completed":
                raise HTTPException(400, "Conversion not yet completed")
            
            output_file = Path(status.output_files[0])
            if not output_file.exists():
                raise HTTPException(404, "Audio file not found")
            
            return FileResponse(
                path=output_file,
                filename=output_file.name,
                media_type="audio/mpeg"
            )

        @self.app.get("/demo-voices")
        async def get_demo_voices():
            """Get list of available demo voices."""
            demo_dir = Path(__file__).parent.parent / "static" / "demo_files"
            voices = []
            try:
                for file in demo_dir.glob("*.mp3"):
                    # Extract name and country from filename (e.g., "en-US-JennyNeural.mp3")
                    match = re.match(r'en-(\w+)-(\w+)Neural\.mp3', file.name)
                    if match:
                        country = match.group(1)
                        name = match.group(2)
                        voices.append({
                            "file": file.name,
                            "name": name,
                            "country": country
                        })
                return sorted(voices, key=lambda x: (x["country"], x["name"]))
            except Exception as e:
                logger.error(f"Error listing demo voices: {str(e)}")
                raise HTTPException(500, "Error listing demo voices")

        # @self.app.get("/static/demo_files/{filename}")
        # async def serve_demo_file(filename: str):
        #     """Serve demo audio files."""
        #     demo_dir = Path(__file__).parent.parent / "static" / "demo_files"
        #     file_path = demo_dir / filename
            
        #     if not file_path.exists():
        #         logger.error(f"Demo file not found: {file_path}")
        #         raise HTTPException(404, "Demo file not found")
                
        #     logger.info(f"Serving demo file: {file_path}")
        #     return FileResponse(
        #         path=file_path,
        #         media_type="audio/mpeg",
        #         filename=filename
        #     )