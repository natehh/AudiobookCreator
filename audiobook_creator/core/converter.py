import os
import re
import uuid
import asyncio
import pyttsx3
from pathlib import Path
from ..utils.nltk_setup import setup_nltk
from ..utils.ebook import get_chapters, get_book_title, get_book_metadata
from ..core.store import ConversionStore
import logging
from pydub import AudioSegment
from mutagen.mp4 import MP4

logger = logging.getLogger()
logging.basicConfig(level=logging.INFO)

class AudiobookConverter:
    def __init__(self, file_path: str, output_dir: str, store: ConversionStore):
        self.file_path = file_path
        self.output_dir = output_dir
        self.store = store
        self.conversion_id = str(uuid.uuid4())
        metadata = get_book_metadata(Path(file_path))
        self.author = metadata["author"]

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
            
            chapter_files = []
            processed_chars = 0
            for i, (title, content) in enumerate(chapters, 1):
                temp_file, title, duration = await self._process_single_chapter(
                    i, title, content, book_dir, processed_chars, total_chars
                )
                chapter_files.append((temp_file, title, duration))
                processed_chars += len(content)
                logger.info(f"Completed chapter {i}")

            final_file = self._create_m4b(book_dir, book_title, chapter_files)
            self.store.update(
                self.conversion_id,
                output_files=[final_file],
                status="completed",
            )
            
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
        """Process a single chapter and save as temporary WAV."""
        temp_file = os.path.join(book_dir, f"temp_{chapter_num:02d}.wav")
        
        if not os.path.exists(temp_file):
            try:
                engine = pyttsx3.init()
                engine.setProperty('rate', 150)
                engine.save_to_file(content, temp_file)
                engine.runAndWait()
                engine.stop()
                del engine
                
                progress = (processed_chars + len(content)) / total_chars
                logger.info(f"{progress*100}% of book converted")
                self.store.update(
                    self.conversion_id,
                    progress=progress,
                )
                
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(f"Error processing chapter {chapter_num}: {str(e)}", exc_info=True)
                raise
        
        return temp_file, title, len(AudioSegment.from_wav(temp_file))
    
    def _create_m4b(self, book_dir, book_title, chapter_files):
        """Combine chapter files into single M4B with chapters and metadata."""
        output_file = os.path.join(book_dir, f"{book_title}.m4b")
        
        # Combine audio files
        combined = AudioSegment.empty()
        chapter_times = []
        total_time = 0
        
        for temp_file, title, duration in chapter_files:
            chapter_times.append((total_time, title))
            audio = AudioSegment.from_wav(temp_file)
            combined += audio
            total_time += duration
            os.remove(temp_file)
        
        # Export as M4B
        combined.export(output_file, format='ipod')
        
        # Add chapters and metadata
        audio = MP4(output_file)
        
        chaps = []
        for i, (start_time, title) in enumerate(chapter_times):
            end_time = chapter_times[i+1][0] if i < len(chapter_times)-1 else total_time
            chaps.extend([
                str(start_time),
                str(end_time),
                title
            ])
        
        audio.tags['©chp'] = chaps
        
        audio['\xa9nam'] = [book_title]
        if hasattr(self, 'author'):
            audio['\xa9ART'] = [self.author]
        
        audio.save()
        
        return output_file