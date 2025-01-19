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
from zipfile import ZipFile
import tempfile

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
            output_dir: str = "output"
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
            
            background_tasks.add_task(converter.convert)
            
            return status

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
            
            with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as tmp:
                with ZipFile(tmp.name, 'w') as zip_file:
                    for output_file in status.output_files:
                        file_path = Path(output_file)
                        if file_path.exists():
                            zip_file.write(file_path, file_path.name)
                        else:
                            raise HTTPException(404, f"Audio file {file_path.name} not found")
                
                return FileResponse(
                    path=tmp.name,
                    filename=f"audiobook_{conversion_id}.zip",
                    media_type="application/zip",
                    background=BackgroundTasks().add_task(lambda: os.unlink(tmp.name))
                )