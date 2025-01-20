from pathlib import Path
from typing import List, Tuple
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup
import mobi
import shutil

def get_chapters(filepath: Path) -> List[Tuple[str, str]]:
    """Extract chapters from various ebook formats."""
    suffix = filepath.suffix.lower()
    
    if suffix == '.epub':
        return _extract_epub_chapters(filepath)
    elif suffix == '.mobi':
        return _extract_mobi_chapters(filepath)
    else:
        return _extract_text_chapters(filepath)

def get_book_title(filepath: Path) -> str:
    """Extract book title from various ebook formats."""
    suffix = filepath.suffix.lower()
    
    if suffix == '.epub':
        return _get_epub_title(filepath)
    elif suffix == '.mobi':
        return _get_mobi_title(filepath)
    else:
        return filepath.stem.replace(" ", "_")

def _extract_epub_chapters(filepath: Path) -> List[Tuple[str, str]]:
    """Extract chapters from EPUB file."""
    book = epub.read_epub(str(filepath))
    chapters = []
    
    for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
        soup = BeautifulSoup(item.content, 'html.parser')
        
        chapter_heads = soup.find_all(['h1', 'h2', 'h3'])
        
        if chapter_heads:
            for head in chapter_heads:
                content = _extract_chapter_content(head)
                if content:
                    chapters.append((
                        head.get_text().strip() or f"Chapter {len(chapters) + 1}",
                        content
                    ))
        else:
            text = soup.get_text().strip()
            if text:
                chapters.append((f"Chapter {len(chapters) + 1}", text))
    
    if not chapters:
        all_text = ' '.join(soup.get_text().strip() 
                          for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT))
        if all_text:
            chapters = [("Chapter 1", all_text)]
            
    if not chapters:
        raise ValueError("No content found in EPUB file")
        
    return chapters

def _extract_mobi_chapters(filepath: Path) -> List[Tuple[str, str]]:
    """Extract chapters from MOBI file."""
    tempdir, mobipath = mobi.extract(str(filepath))
    try:
        return get_chapters(Path(mobipath))
    finally:
        shutil.rmtree(tempdir)

def _extract_text_chapters(filepath: Path) -> List[Tuple[str, str]]:
    """Extract content from text file as a single chapter."""
    text = filepath.read_text(encoding='utf-8')
    return [("Chapter 1", text)]

def _extract_chapter_content(head_tag) -> str:
    """Extract chapter content following a heading tag."""
    content = []
    current = head_tag.next_sibling
    while current and not (isinstance(current, BeautifulSoup) 
                         and current.name in ['h1', 'h2', 'h3']):
        if hasattr(current, 'get_text'):
            text = current.get_text().strip()
            if text:
                content.append(text)
        current = current.next_sibling
    return ' '.join(content).strip()

def _get_epub_title(filepath: Path) -> str:
    """Extract title from EPUB metadata."""
    book = epub.read_epub(str(filepath))
    return book.get_metadata('DC', 'title')[0][0].replace(" ", "_") or filepath.stem.replace(" ", "_")

def _get_mobi_title(filepath: Path) -> str:
    """Extract title from MOBI file."""
    tempdir, mobipath = mobi.extract(str(filepath))
    try:
        return get_book_title(Path(mobipath)).replace(" ", "_")
    finally:
        shutil.rmtree(tempdir)

def get_book_metadata(filepath: Path) -> dict:
    """Extract book metadata from various formats."""
    suffix = filepath.suffix.lower()
    
    if suffix == '.epub':
        book = epub.read_epub(str(filepath))
        creator = book.get_metadata('DC', 'creator')
        author = creator[0][0] if creator else "Unknown Author"
        title = book.get_metadata('DC', 'title')[0][0]
        return {"title": title, "author": author}
    elif suffix == '.mobi':
        return {"title": filepath.stem, "author": "Unknown Author"}
    else:
        return {"title": filepath.stem, "author": "Unknown Author"}