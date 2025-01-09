import platform
import ssl
import sys
from pathlib import Path
from typing import List

import nltk

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
    return filepath.read_text(encoding='utf-8')

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

def text_to_speech(sentences: List[str]) -> None:
    """Convert sentences to speech using pyttsx3."""
    engine = initialize_tts_engine()
    for sentence in sentences:
        try:
            engine.say(sentence)
            engine.runAndWait()
        except Exception as e:
            print(f"Error processing sentence: {e}")
            continue

def main(filepath: str) -> None:
    """Main function to process text file and convert to speech."""
    try:
        setup_nltk()
        text = load_text(Path(filepath))
        sentences = split_into_sentences(text)
        text_to_speech(sentences)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main("test_text.txt")