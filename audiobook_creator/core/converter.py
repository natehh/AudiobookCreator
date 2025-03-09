import os
import re
import uuid
import asyncio
from pathlib import Path
from ..utils.nltk_setup import setup_nltk
from ..utils.ebook import get_chapters, get_book_title, get_book_metadata
from ..core.store import ConversionStore
import logging
from pydub import AudioSegment
from mutagen.mp4 import MP4
import edge_tts
import aiofiles
from sqlalchemy.orm import Session
from ..core.database import get_db, Conversion
from ..core.tts_service import TTSService
from datetime import datetime, timedelta
from ..utils.cleanup import sanitize_path
import subprocess

logger = logging.getLogger()
logging.basicConfig(level=logging.INFO)

class AudiobookConverter:
    def __init__(self, file_path: str, output_dir: str, store: ConversionStore, voice_id: str):
        self.file_path = file_path
        self.output_dir = output_dir
        self.store = store
        self.conversion_id = str(uuid.uuid4())
        self.voice_id = voice_id
        metadata = get_book_metadata(Path(file_path))
        self.author = metadata["author"]
        self.tts_service = TTSService()

    def sanitize_filename(self, filename):
        """
        Sanitize a filename for safe use in file operations.
        
        Args:
            filename: The filename to sanitize
            
        Returns:
            A sanitized filename
        """
        # Use the common sanitize_path function
        valid_name = sanitize_path(filename)
        
        # Ensure it has a .wav extension if needed
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
        db = next(get_db())  # Get a database session
        try:
            setup_nltk()
            
            book_title = get_book_title(Path(self.file_path))
            logger.info(f"Found book title: {book_title}")
            chapters = get_chapters(Path(self.file_path))
            logger.info(f"Found {len(chapters)} chapters")
            
            total_chars = sum(len(content) for _, content in chapters)
            logger.info(f"Total characters to process: {total_chars}")
            
            # Extract voice name from voice_id (e.g., "en-US-JennyNeural" -> "Jenny")
            voice_name = re.search(r'-(\w+)Neural$', self.voice_id)
            voice_name = voice_name.group(1) if voice_name else 'Unknown'
            
            # Create directory with book title and voice name
            book_dir = os.path.join(self.output_dir, 
                                re.sub(r'[<>:"/\\|?*]', '_', f"{book_title} ({voice_name})"))
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

                # Update progress in the database
                progress = processed_chars / total_chars
                db.query(Conversion).filter(Conversion.id == self.conversion_id).update(
                    {"progress": progress}
                )
                db.commit()

            final_file = self._create_m4b(book_dir, f"{book_title} ({voice_name})", chapter_files)
            self.store.update(
                self.conversion_id,
                output_files=[final_file],
                status="completed",
            )

            # Update status in the database
            db.query(Conversion).filter(Conversion.id == self.conversion_id).update(
                {"status": "completed"}
            )
            db.commit()
            
        except Exception as e:
            logger.error(f"Conversion error: {str(e)}", exc_info=True)
            self.store.update(
                self.conversion_id,
                status="failed",
                error=str(e)
            )

            # Update status in the database
            db.query(Conversion).filter(Conversion.id == self.conversion_id).update(
                {"status": "failed"}
            )
            db.commit()
            raise
        finally:
            await self.cleanup()
            db.close()


    async def _process_single_chapter(self, chapter_num, title, content, book_dir, processed_chars, total_chars):
        """Process a single chapter and save as MP3."""
        temp_file = os.path.join(book_dir, f"temp_{chapter_num:02d}.mp3")
        
        if not os.path.exists(temp_file):
            try:
                await self.tts_service.convert_text(
                    text=content,
                    voice_id=self.voice_id,
                    output_path=Path(temp_file)
                )
                
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
        
        return temp_file, title, len(AudioSegment.from_mp3(temp_file))
    
    def _create_m4b(self, book_dir, book_title, chapter_files):
        """Combine chapter files into single M4B with chapters and metadata."""
        output_file = os.path.join(book_dir, f"{book_title}.m4b")
        logger.info(f"Creating M4B file at: {output_file}")
        
        # Create a temporary file listing all chapters for ffmpeg concat
        concat_file = os.path.join(book_dir, "chapters.txt")
        chapter_times = []
        total_time = 0
        
        try:
            # Write the concat file for ffmpeg
            with open(concat_file, "w", encoding="utf-8") as f:
                for temp_file, title, duration in chapter_files:
                    # Store chapter timing info
                    chapter_times.append((total_time, title))
                    # Write file entry in ffmpeg concat format
                    f.write(f"file '{os.path.abspath(temp_file)}'\n")
                    total_time += duration
            
            # Write ffmetadata file with chapters and global metadata
            meta_file = os.path.join(book_dir, "ffmetadata.txt")
            with open(meta_file, "w", encoding="utf-8") as f:
                f.write(";FFMETADATA1\n")
                f.write(f"title={book_title}\n")
                if hasattr(self, 'author'):
                    f.write(f"artist={self.author}\n")
                f.write("\n")
                
                for i, (start, chap_title) in enumerate(chapter_times):
                    end = chapter_times[i+1][0] if i+1 < len(chapter_times) else total_time
                    f.write("[CHAPTER]\n")
                    f.write("TIMEBASE=1/1000\n")
                    f.write(f"START={start}\n")
                    f.write(f"END={end}\n")
                    f.write(f"title={chap_title}\n\n")
            
            # Use ffmpeg to concatenate files and embed metadata in a single operation
            # Convert to AAC audio (required for M4B) with appropriate quality settings
            cmd = (
                f'ffmpeg -y -nostdin -threads 0 -f concat -safe 0 -i "{concat_file}" '
                f'-i "{meta_file}" -map_metadata 1 '
                f'-c:a aac -b:a 64k -ar 44100 -af "aresample=resampler=soxr" '  # High quality resampling
                f'-movflags +faststart "{output_file}"'
            )
            
            logger.info("Starting FFmpeg processing...")
            # Set lower process priority to prevent system overload
            if os.name == 'posix':  # Unix-like systems
                cmd = f'nice -n 10 {cmd}'
            
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                error_msg = f"FFmpeg failed: {result.stderr}"
                logger.error(error_msg)
                raise RuntimeError(error_msg)
            
            logger.info("FFmpeg processing completed successfully")
            
            # Clean up chapter files and temporary files
            for temp_file, _, _ in chapter_files:
                try:
                    os.remove(temp_file)
                except OSError as e:
                    logger.warning(f"Failed to remove temporary file {temp_file}: {e}")
            
            # Clean up metadata and concat files
            for cleanup_file in [meta_file, concat_file]:
                try:
                    os.remove(cleanup_file)
                except OSError as e:
                    logger.warning(f"Failed to remove temporary file {cleanup_file}: {e}")
            
            return output_file
            
        except Exception as e:
            logger.error(f"Error during M4B creation: {str(e)}", exc_info=True)
            # Clean up any temporary files that might exist
            for file in [concat_file, meta_file, output_file]:
                if os.path.exists(file):
                    try:
                        os.remove(file)
                    except OSError:
                        pass
            raise