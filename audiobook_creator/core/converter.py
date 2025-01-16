import os
import re
import uuid
import asyncio
import pyttsx3
from pathlib import Path
from ..utils.nltk_setup import setup_nltk
from ..utils.ebook import get_chapters, get_book_title
from ..core.store import ConversionStore
import logging

logger = logging.getLogger()
logging.basicConfig(level=logging.INFO)

class AudiobookConverter:
    """Handles the conversion of ebooks to audiobooks."""
    def __init__(self, file_path: str, output_dir: str, store: ConversionStore):
        self.file_path = file_path
        self.output_dir = output_dir
        self.store = store
        self.conversion_id = str(uuid.uuid4())
        
    async def cleanup(self):
        """Remove temporary uploaded file."""
        if os.path.exists(self.file_path):
            try:
                logger.info(f"Removing {self.file_path}")
                os.remove(self.file_path)
            except OSError as e:
                logger.error(f"Error cleaning up {self.file_path}: {e}")
        
    async def convert(self):
        """Convert ebook to audiobook chapters."""
        try:
            setup_nltk()
            book_title = get_book_title(Path(self.file_path))
            logger.info(f"Found book title: {book_title}")
            chapters = get_chapters(Path(self.file_path))
            
            book_dir = os.path.join(self.output_dir, 
                                  re.sub(r'[<>:"/\\|?*]', '_', book_title))
            os.makedirs(book_dir, exist_ok=True)
            
            await self._process_chapters(chapters, book_dir)
            
            self.store.update(self.conversion_id, status="completed")
            
        except Exception as e:
            self.store.update(
                self.conversion_id,
                status="failed",
                error=str(e)
            )
            raise
        finally:
            await self.cleanup()
    
    async def _process_chapters(self, chapters, book_dir):
        """Process individual chapters and convert to audio."""
        total_words = sum(len(content.split()) for _, content in chapters)
        processed_words = 0
        
        engine = pyttsx3.init()
        engine.say(".")  # TODO: remove when ttsx3 bug is fixed
        
        for i, (title, content) in enumerate(chapters, 1):
            safe_title = re.sub(r'[<>:"/\\|?*]', '_', title)
            output_file = os.path.join(book_dir, f"{i:02d}_{safe_title}.wav")
            
            engine.save_to_file(content, output_file)
            engine.runAndWait()
            
            processed_words += len(content.split())
            progress = (processed_words / total_words) * 100
            
            self.store.update(
                self.conversion_id,
                progress=progress,
                output_files=[*self.store.get(self.conversion_id).output_files, 
                            output_file]
            )
            
            await asyncio.sleep(0)
        
        engine.stop()