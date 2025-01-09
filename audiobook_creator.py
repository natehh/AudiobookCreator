import platform
import ssl
import sys
from pathlib import Path
from typing import List
import nltk
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup
import mobi
import shutil
import contextlib
from gtts import gTTS
import os

def setup_nltk():
    """Setup NLTK with SSL workaround for downloads."""
    try:
        _create_unverified_https_context = ssl._create_unverified_context
    except AttributeError:
        pass
    else:
        ssl._create_default_https_context = _create_unverified_https_context
    
    nltk.download('punkt', quiet=True)

def load_text(filepath: Path) -> str:
    """Read text content from file."""
    suffix = filepath.suffix.lower()
    
    if suffix == '.txt':
        return filepath.read_text(encoding='utf-8')
    elif suffix == '.epub':
        book = epub.read_epub(str(filepath))
        text = ''
        for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
            soup = BeautifulSoup(item.content, 'html.parser')
            text += soup.get_text() + '\n'
        return text
    elif suffix == '.mobi':
        tempdir, mobipath = mobi.extract(str(filepath))
        try:
            return load_text(Path(mobipath))
        finally:
            shutil.rmtree(tempdir)
    else:
        raise ValueError(f"Unsupported file format: {suffix}")

def split_into_sentences(text: str) -> List[str]:
    """Split text into sentences using NLTK."""
    return nltk.sent_tokenize(text)

def initialize_tts_engine():
    """Initialize text-to-speech engine with platform-specific settings."""
    if platform.system() == 'Darwin':  # macOS
        try:
            # Import required packages for macOS
            import objc
            import AppKit
            import Foundation
        except ImportError:
            print("Error: Missing required macOS packages.")
            print("Please install all required packages with:")
            print("pip install pyobjc-core pyobjc-framework-Cocoa pyobjc-framework-ApplicationServices pyobjc-framework-CoreText")
            sys.exit(1)

    try:
        import pyttsx3
        engine = pyttsx3.init()
        engine.say("Testing speech engine")
        engine.runAndWait()
        return engine
    except Exception as e:
        print(f"Error: Could not initialize speech engine: {e}")
        sys.exit(1)

def text_to_speech(sentences: List[str], output_file: str = "output.mp3") -> None:
    """Convert sentences to speech and save as MP3."""
    # Join sentences with spaces to create natural pauses
    full_text = ' '.join(sentences)
    
    try:
        tts = gTTS(text=full_text, lang='en')
        tts.save(output_file)
        print(f"Audio saved to {output_file}")
    except Exception as e:
        print(f"Error creating audio file: {e}")

def main(filepath: str, output_file: str = "output.mp3") -> None:
    """Main function to process text file and convert to speech."""
    try:
        setup_nltk()
        text = load_text(Path(filepath))
        sentences = split_into_sentences(text)
        text_to_speech(sentences, output_file)
    except KeyboardInterrupt:
        print("\nProcess interrupted by user")
        if os.path.exists(output_file):
            os.remove(output_file)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main("test_text.txt")