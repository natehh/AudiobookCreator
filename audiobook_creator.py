import platform
import ssl
import sys
import subprocess
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

class MacTTS:
    """Text-to-speech engine for macOS using built-in 'say' command."""
    def say(self, text):
        subprocess.run(['say', text])
    
    def runAndWait(self):
        pass  # 'say' command is blocking, no need to wait

class LinuxTTS:
    """Text-to-speech engine for Linux and other platforms using pyttsx3."""
    def __init__(self):
        import pyttsx3
        self.engine = pyttsx3.init()
    
    def say(self, text):
        self.engine.say(text)
    
    def runAndWait(self):
        self.engine.runAndWait()

def initialize_tts_engine():
    """Initialize platform-specific text-to-speech engine."""
    if platform.system() == 'Darwin':
        return MacTTS()
    else:
        return LinuxTTS()

def text_to_speech(sentences: List[str]) -> None:
    """Convert sentences to speech using platform-specific TTS."""
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