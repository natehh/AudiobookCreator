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
    def __init__(self, file_path: str, output_dir: str, store: ConversionStore):
        self.file_path = file_path
        self.output_dir = output_dir
        self.store = store
        self.conversion_id = str(uuid.uuid4())

    def sanitize_filename(self, filename):
        valid_name = "".join(c for c in filename if c.isalnum() or c in "._- ").replace(" ", "_")
        if not valid_name.endswith('.wav'):
            valid_name += '.wav'
        return valid_name
        
    async def cleanup(self):
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
            logger.info(f"Found {len(chapters)} chapters")
            
            total_chars = sum(len(content) for _, content in chapters)
            logger.info(f"Total characters to process: {total_chars}")
            
            book_dir = os.path.join(self.output_dir, 
                                re.sub(r'[<>:"/\\|?*]', '_', book_title))
            os.makedirs(book_dir, exist_ok=True)
            logger.info(f"Created book directory: {book_dir}")
            
            processed_chars = 0
            for i, (title, content) in enumerate(chapters, 1):
                logger.info(f"Starting chapter {i}: {title}")
                await self._process_single_chapter(i, title, content, book_dir, processed_chars, total_chars)
                processed_chars += len(content)
                logger.info(f"Completed chapter {i}")
            
            self.store.update(self.conversion_id, status="completed")
            
        except Exception as e:
            logger.error(f"Conversion error: {str(e)}", exc_info=True)
            self.store.update(
                self.conversion_id,
                status="failed",
                error=str(e)
            )
            raise
        finally:
            await self.cleanup()

    async def _process_single_chapter(self, chapter_num, title, content, book_dir, processed_chars, total_chars):
        """Process a single chapter with its own engine instance."""
        safe_title = self.sanitize_filename(title)
        output_file = os.path.join(book_dir, f"{chapter_num:02d}_{safe_title}")

        if os.path.exists(output_file):
            logger.info(f"Chapter {chapter_num} already exists, skipping: {output_file}")
            self.store.update(
                self.conversion_id,
                progress=(processed_chars + len(content)) / total_chars,
                output_files=[*self.store.get(self.conversion_id).output_files, 
                            output_file]
            )
            return
        
        try:
            engine = pyttsx3.init()
            engine.setProperty('rate', 150)
            
            engine.save_to_file(content, output_file)
            engine.runAndWait()
            
            progress = (processed_chars + len(content)) / total_chars
            logger.info(f"{progress*100}% of book converted")
            self.store.update(
                self.conversion_id,
                progress=progress,
                output_files=[*self.store.get(self.conversion_id).output_files, 
                            output_file]
            )
            
            engine.stop()
            del engine
            
            await asyncio.sleep(1)
            
        except Exception as e:
            logger.error(f"Error processing chapter {chapter_num}: {str(e)}", exc_info=True)
            raise