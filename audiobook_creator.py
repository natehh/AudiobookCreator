import ssl
from pathlib import Path
from typing import List
import nltk
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup
import mobi
import shutil
import os
import re
import pyttsx3
import time
from datetime import datetime, timedelta

def setup_nltk():
    try:
        _create_unverified_https_context = ssl._create_unverified_context
    except AttributeError:
        pass
    else:
        ssl._create_default_https_context = _create_unverified_https_context
    
    nltk.download('punkt', quiet=True)

def get_chapters(filepath: Path) -> List[tuple[str, str]]:
    suffix = filepath.suffix.lower()
    
    if suffix == '.epub':
        book = epub.read_epub(str(filepath))
        chapters = []
        
        for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
            soup = BeautifulSoup(item.content, 'html.parser')
            
            chapter_heads = soup.find_all(['h1', 'h2', 'h3'])
            
            if chapter_heads:
                for head in chapter_heads:
                    content = []
                    current = head.next_sibling
                    while current and not (isinstance(current, BeautifulSoup) and current.name in ['h1', 'h2', 'h3']):
                        if hasattr(current, 'get_text'):
                            text = current.get_text().strip()
                            if text:
                                content.append(text)
                        current = current.next_sibling
                    
                    chapter_text = ' '.join(content).strip()
                    if chapter_text:
                        chapters.append((
                            head.get_text().strip() or f"Chapter {len(chapters) + 1}",
                            chapter_text
                        ))
            else:
                text = soup.get_text().strip()
                if text:
                    chapters.append((
                        f"Chapter {len(chapters) + 1}",
                        text
                    ))
        
        if not chapters:
            all_text = ' '.join(soup.get_text().strip() for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT))
            if all_text:
                chapters = [("Chapter 1", all_text)]
                
        if not chapters:
            raise ValueError("No content found in EPUB file")
            
        return chapters
        
    elif suffix == '.mobi':
        tempdir, mobipath = mobi.extract(str(filepath))
        try:
            return get_chapters(Path(mobipath))
        finally:
            shutil.rmtree(tempdir)
            
    else:
        text = filepath.read_text(encoding='utf-8')
        return [("Chapter 1", text)]

def get_book_title(filepath: Path) -> str:
   suffix = filepath.suffix.lower()
   
   if suffix == '.epub':
       book = epub.read_epub(str(filepath))
       return book.get_metadata('DC', 'title')[0][0].replace(" ", "_") or filepath.stem.replace(" ", "_")
   elif suffix == '.mobi':
       tempdir, mobipath = mobi.extract(str(filepath))
       try:
           return get_book_title(Path(mobipath)).replace(" ", "_")
       finally:
           shutil.rmtree(tempdir)
   else:
       return filepath.stem.replace(" ", "_")

class ProgressTracker:
    def __init__(self, total_chapters: int, total_words: int):
        self.total_chapters = total_chapters
        self.total_words = total_words
        self.current_chapter = 0
        self.processed_words = 0
        self.start_time = datetime.now()
    
    def update(self, chapter_words: int):
        self.current_chapter += 1
        self.processed_words += chapter_words
        
        progress = (self.processed_words / self.total_words) * 100
        
        elapsed_time = datetime.now() - self.start_time
        if self.processed_words > 0:
            words_per_second = self.processed_words / elapsed_time.total_seconds()
            remaining_words = self.total_words - self.processed_words
            estimated_remaining_seconds = remaining_words / words_per_second if words_per_second > 0 else 0
            eta = timedelta(seconds=int(estimated_remaining_seconds))
        else:
            eta = timedelta(0)
        
        print(f"\r{' ' * 80}", end="\r")  # Clear line
        print(
            f"Progress: {progress:.1f}% | "
            f"Chapter: {self.current_chapter}/{self.total_chapters} | "
            f"Time elapsed: {str(elapsed_time).split('.')[0]} | "
            f"Estimated Time Remaining: {str(eta).split('.')[0]}", 
            end="\r"
        )

def text_to_speech(chapters: List[tuple[str, str]], book_title: str, output_dir: str = "output") -> None:
    book_dir = os.path.join(output_dir, re.sub(r'[<>:"/\\|?*]', '_', book_title))
    os.makedirs(book_dir, exist_ok=True)
    
    total_words = sum(len(content.split()) for _, content in chapters)
    progress = ProgressTracker(len(chapters), total_words)
    
    engine = pyttsx3.init()
    engine.say(".") # TODO: remove when ttsx3 comes out
    
    current_file = None
    try:
        for i, (title, content) in enumerate(chapters, 1):
            safe_title = re.sub(r'[<>:"/\\|?*]', '_', title)
            current_file = os.path.join(book_dir, f"{i:02d}_{safe_title}.wav")
            
            engine.save_to_file(content, current_file)
            engine.runAndWait()
            
            progress.update(len(content.split()))
            current_file = None
            
        print("\nConversion completed successfully!")
        engine.stop()
            
    except Exception as e:
        if current_file and os.path.exists(current_file):
            os.remove(current_file)
        raise e

def main(filepath: str, output_dir: str = "output") -> None:
    try:
        setup_nltk()
        book_title = get_book_title(Path(filepath))
        chapters = get_chapters(Path(filepath))
        text_to_speech(chapters, book_title, output_dir)
    except KeyboardInterrupt:
        print("\nProcess interrupted by user")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main("artofwar.epub")