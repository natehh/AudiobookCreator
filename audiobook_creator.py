import ssl
from pathlib import Path
from typing import List
import nltk
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup
import mobi
import shutil
from gtts import gTTS
import os
import re

def setup_nltk():
    """Setup NLTK with SSL workaround for downloads."""
    try:
        _create_unverified_https_context = ssl._create_unverified_context
    except AttributeError:
        pass
    else:
        ssl._create_default_https_context = _create_unverified_https_context
    
    nltk.download('punkt', quiet=True)

def get_chapters(filepath: Path) -> List[tuple[str, str]]:
    """Extract chapters as (title, content) tuples."""
    suffix = filepath.suffix.lower()
    
    if suffix == '.epub':
        book = epub.read_epub(str(filepath))
        chapters = []
        
        for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
            soup = BeautifulSoup(item.content, 'html.parser')
            
            # Look for common chapter heading patterns
            chapter_heads = soup.find_all(['h1', 'h2', 'h3'])
            
            if chapter_heads:
                for head in chapter_heads:
                    # Get all content until next heading
                    content = []
                    current = head.next_sibling
                    while current and not (isinstance(current, BeautifulSoup) and current.name in ['h1', 'h2', 'h3']):
                        if hasattr(current, 'get_text'):
                            text = current.get_text().strip()
                            if text:
                                content.append(text)
                        current = current.next_sibling
                    
                    chapter_text = ' '.join(content).strip()
                    if chapter_text:  # Only add if there's content
                        chapters.append((
                            head.get_text().strip() or f"Chapter {len(chapters) + 1}",
                            chapter_text
                        ))
            else:
                # If no headings found, use all text content
                text = soup.get_text().strip()
                if text:
                    chapters.append((
                        f"Chapter {len(chapters) + 1}",
                        text
                    ))
        
        # If no chapters found, treat entire book as one chapter
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
        # For text files, treat as single chapter
        text = filepath.read_text(encoding='utf-8')
        return [("Chapter 1", text)]

def split_into_sentences(text: str) -> List[str]:
    """Split text into sentences using NLTK."""
    return nltk.sent_tokenize(text)

def get_book_title(filepath: Path) -> str:
   """Extract book title from ebook, fallback to filename."""
   suffix = filepath.suffix.lower()
   
   if suffix == '.epub':
       book = epub.read_epub(str(filepath))
       return book.get_metadata('DC', 'title')[0][0] or filepath.stem
   elif suffix == '.mobi':
       tempdir, mobipath = mobi.extract(str(filepath))
       try:
           return get_book_title(Path(mobipath))
       finally:
           shutil.rmtree(tempdir)
   else:
       return filepath.stem

def text_to_speech(chapters: List[tuple[str, str]], book_title: str, output_dir: str = "output") -> None:
    """Convert chapters to speech files in book-specific directory."""
    book_dir = os.path.join(output_dir, re.sub(r'[<>:"/\\|?*]', '_', book_title))
    os.makedirs(book_dir, exist_ok=True)
    
    current_file = None  # Track current file being processed
    try:
        for i, (title, content) in enumerate(chapters, 1):
            safe_title = re.sub(r'[<>:"/\\|?*]', '_', title)
            current_file = os.path.join(book_dir, f"{i:02d}_{safe_title}.mp3")
            
            tts = gTTS(text=content, lang='en')
            tts.save(current_file)
            print(f"Saved: {current_file}")
            current_file = None  # Reset after successful save
            
    except Exception as e:
        if current_file and os.path.exists(current_file):
            os.remove(current_file)
        raise e

def main(filepath: str, output_dir: str = "output") -> None:
    """Main function to process ebook and convert to speech."""
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
    main("test_text.txt")