import os
import uuid
from fastapi import FastAPI, UploadFile, HTTPException, BackgroundTasks, Depends, Form, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi import WebSocket
from pathlib import Path
from ..core.converter import AudiobookConverter
from ..core.store import ConversionStore
from .models import ConversionStatus
from sqlalchemy.orm import Session
from ..core.database import get_db, Conversion, get_or_create_user, User, Payment, Usage
from ..utils.ebook import get_book_metadata
from ..utils.email_utils import send_email
from ..utils.file_validation import validate_file_upload, save_validated_file
from .auth.tokens import JWTBearer, JWTHandler
from ..utils.cleanup import sanitize_path
from ..utils.rate_limit import conversion_rate_limit, general_rate_limit
import re
import logging
from pydantic import BaseModel
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

class FeedbackRequest(BaseModel):
    message: str
    includeEmail: bool
    email: str = None

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
        # Get allowed origins from environment or use a default
        allowed_origins = os.getenv('ALLOWED_ORIGINS', 'http://localhost:8000').split(',')
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=allowed_origins,
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
            voice_id: str = Form(...),
            payment_id: int = Form(...),
            token: str = Depends(JWTBearer()),
            output_dir: str = "output",
            db: Session = Depends(get_db),
            _: bool = Depends(conversion_rate_limit)  # Add rate limiting
        ):
            # Ensure tmp directory exists
            os.makedirs("tmp", exist_ok=True)
            
            # Validate file security
            try:
                await validate_file_upload(file)
            except HTTPException as e:
                logger.error(f"File validation failed: {e.detail}")
                raise e
            
            # Get user from token
            user_email = JWTHandler.verify_token(token, check_type="access")
            user = get_or_create_user(db, {"email": user_email})
            
            # For free conversions (payment_id = 0), skip payment verification
            payment = None
            if payment_id == 0:
                # Create a free payment record for tracking
                payment = Payment(
                    user_id=user.id,
                    amount=0,
                    status='succeeded'
                )
                db.add(payment)
                db.commit()
                db.refresh(payment)  # Get the generated ID
            else:
                # Verify payment for paid conversions
                payment = db.query(Payment).filter(
                    Payment.id == payment_id,
                    Payment.user_id == user.id,
                    Payment.status == 'pending'
                ).first()
                
                if not payment:
                    raise HTTPException(400, "Invalid or expired payment")
                
                # Update payment status
                payment.status = 'succeeded'
                db.commit()
            
            # Generate a safe temporary file path with UUID
            file_ext = os.path.splitext(file.filename)[1]
            sanitized_filename = sanitize_path(file.filename)
            temp_path = os.path.join("tmp", f"temp_{uuid.uuid4()}_{sanitized_filename}")
            
            # Save the file securely
            await save_validated_file(file, temp_path)
            
            converter = AudiobookConverter(
                temp_path, 
                output_dir, 
                self.store,
                voice_id
            )
            
            status = ConversionStatus(
                id=converter.conversion_id,
                status="processing",
                progress=0.0,
                temp_file=temp_path
            )
            self.store.add(status)
            
            # Get book metadata
            book_metadata = get_book_metadata(Path(temp_path))
            
            # Create a new conversion record with expiration date
            conversion = Conversion(
                id=converter.conversion_id,
                user_id=user.id,
                title=book_metadata["title"],
                author=book_metadata["author"],
                input_size=os.path.getsize(temp_path),
                status="processing",
                progress=0.0,
                voice_id=voice_id,
                expiration_date=datetime.now(timezone.utc) + timedelta(hours=24)
            )
            db.add(conversion)
            
            # Create usage record
            usage = Usage(
                user_id=user.id,
                characters_processed=book_metadata.get("char_count", 0),
                amount_charged=payment.amount,
                payment_id=payment.id
            )
            db.add(usage)
            db.commit()
            
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

        @self.app.get("/download/{conversion_id}")
        async def download_audiobook(
            conversion_id: str,
            token: str = Depends(JWTBearer()),
            db: Session = Depends(get_db),
            _: bool = Depends(general_rate_limit)  # Add rate limiting
        ):
            # Get user from token
            email = JWTHandler.verify_token(token)
            user = db.query(User).filter(User.email == email).first()
            
            if not user:
                raise HTTPException(status_code=404, detail="User not found")
            
            # Get conversion from database
            conversion = db.query(Conversion).filter(
                Conversion.id == conversion_id,
                Conversion.user_id == user.id
            ).first()
            
            if not conversion:
                raise HTTPException(404, "Conversion not found")
            
            if conversion.status != "completed":
                raise HTTPException(400, "Conversion not yet completed")
            
            # Check if audiobook has expired
            if conversion.expiration_date:
                # Convert naive datetime to UTC
                expiration_utc = conversion.expiration_date.replace(tzinfo=timezone.utc)
                if expiration_utc < datetime.now(timezone.utc):
                    raise HTTPException(400, "Audiobook has expired")
            
            # Sanitize book title and voice name
            book_title = sanitize_path(conversion.title)
            
            # Sanitize voice name extraction
            voice_match = re.search(r'-(\w+)Neural$', conversion.voice_id)
            voice_name = voice_match.group(1) if voice_match else 'Unknown'
            voice_name = sanitize_path(voice_name)
            
            # Construct the safe file path to the directory
            dir_name = f"{book_title} ({voice_name})"
            output_dir = Path("/app/output")
            book_dir = output_dir / dir_name
            
            # Try multiple file pattern possibilities
            possible_filenames = [
                f"{book_title}.m4b",
                f"{book_title} ({voice_name}).m4b",
                f"{dir_name}.m4b"
            ]
            
            m4b_file = None
            for filename in possible_filenames:
                possible_file = book_dir / filename
                logger.info(f"Checking for file: {possible_file}")
                if possible_file.exists():
                    m4b_file = possible_file
                    logger.info(f"Found m4b file: {m4b_file}")
                    break
            
            # If no match with expected patterns, search for any .m4b file
            if not m4b_file and book_dir.exists():
                m4b_files = list(book_dir.glob("*.m4b"))
                if m4b_files:
                    m4b_file = m4b_files[0]
                    logger.info(f"Found m4b file via glob: {m4b_file}")
            
            # Validate the file exists and is safe
            if not m4b_file or not m4b_file.exists():
                # Log details for debugging
                logger.error(f"Could not find any m4b file")
                logger.error(f"Directory exists: {book_dir.exists()}")
                if book_dir.exists():
                    logger.error(f"Contents of directory: {list(book_dir.iterdir())}")
                raise HTTPException(404, "Audiobook file not found")
            
            # Validate that the file path is within the output directory (prevent path traversal)
            try:
                real_path = m4b_file.resolve()
                output_dir_resolved = output_dir.resolve()
                
                if output_dir_resolved not in real_path.parents:
                    raise HTTPException(400, "Invalid file path")
                
                logger.info(f"Serving audiobook file: {real_path}")
                return FileResponse(
                    path=real_path,
                    filename=f"{conversion.title}.m4b",
                    media_type="audio/x-m4b"
                )
            except (ValueError, RuntimeError) as e:
                raise HTTPException(400, f"Security error: {str(e)}")

        @self.app.get("/demo-voices")
        async def get_demo_voices():
            """Get list of available demo voices."""
            # Cache the results using FastAPI's caching mechanisms or store in memory
            if hasattr(self, '_cached_voices') and self._cached_voices:
                return self._cached_voices

            demo_dir = Path(__file__).parent.parent / "static" / "demo_files"
            voices = []
            try:
                # Pre-compile the regex pattern
                pattern = re.compile(r'en-(\w+)-(\w+)Neural\.mp3')
                
                # Use a list comprehension for better performance
                voices = [
                    {
                        "file": file.name,
                        "name": match.group(2),
                        "country": match.group(1),
                        "url": f"/static/demo_files/{file.name}"  # Add direct URL
                    }
                    for file in demo_dir.glob("*.mp3")
                    if (match := pattern.match(file.name))
                ]
                
                # Sort and cache the results
                self._cached_voices = sorted(voices, key=lambda x: (x["country"], x["name"]))
                return self._cached_voices
                
            except Exception as e:
                logger.error(f"Error listing demo voices: {str(e)}")
                raise HTTPException(500, "Error listing demo voices")

        @self.app.get("/api/conversions/{conversion_id}")
        async def get_conversion(
            conversion_id: str,
            token: str = Depends(JWTBearer()),
            db: Session = Depends(get_db)
        ):
            # Get user from token
            email = JWTHandler.verify_token(token)
            user = db.query(User).filter(User.email == email).first()
            
            if not user:
                raise HTTPException(status_code=404, detail="User not found")
            
            # Get conversion from database
            conversion = db.query(Conversion).filter(
                Conversion.id == conversion_id,
                Conversion.user_id == user.id
            ).first()
            
            if not conversion:
                raise HTTPException(status_code=404, detail="Conversion not found")
            
            return {
                "id": conversion.id,
                "title": conversion.title,
                "author": conversion.author,
                "status": conversion.status,
                "progress": conversion.progress,
                "created_at": conversion.created_at.isoformat() + "Z",
                "expiration_date": conversion.expiration_date.isoformat() + "Z" if conversion.expiration_date else None,
                "voice": conversion.voice_id
            }

        @self.app.post("/send-feedback")
        async def send_feedback(feedback: FeedbackRequest):
            """Handle feedback form submissions."""
            try:
                # Get the feedback recipient email from environment
                recipient_email = os.getenv("FEEDBACK_EMAIL", os.getenv("EMAIL_ADDRESS"))
                if not recipient_email:
                    raise HTTPException(500, "Feedback email not configured")
                
                # Construct the email body
                body = f"New feedback received:\n\n{feedback.message}"
                if feedback.includeEmail and feedback.email:
                    body += f"\n\nReply to: {feedback.email}"
                
                # Send the email
                send_email(
                    to=recipient_email,
                    subject="New Feedback from AudiobookCreator",
                    body=body
                )
                
                return {"status": "success", "message": "Feedback sent successfully"}
                
            except Exception as e:
                logging.error(f"Error sending feedback: {str(e)}")
                raise HTTPException(500, "Failed to send feedback")
