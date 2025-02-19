from abc import ABC, abstractmethod
import edge_tts
import asyncio
import aiofiles
import os
import json
import re
import nltk
from pathlib import Path
from google.cloud import texttospeech
from dotenv import load_dotenv
from pydub import AudioSegment

# Load environment variables
load_dotenv()

# Download required NLTK data
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt')

def preprocess_text(text: str, max_chars: int = 1000) -> list[str]:
    """Split text into chunks that are safe for TTS processing."""
    # Remove any SSML tags
    text = re.sub(r'<[^>]+>', '', text)
    
    # Split into sentences first
    sentences = nltk.sent_tokenize(text)
    chunks = []
    
    for sentence in sentences:
        # Clean up the sentence
        sentence = sentence.strip()
        
        # Split long sentences by commas and other punctuation
        if len(sentence) > max_chars:
            parts = re.split(r'([,;:—])', sentence)  # Keep the delimiters
            current_part = []
            current_length = 0
            
            for i in range(0, len(parts), 2):
                part = parts[i].strip()
                delimiter = parts[i + 1] if i + 1 < len(parts) else "."
                
                # If this part would exceed the limit, save current and start new
                if current_length + len(part) + 1 > max_chars:
                    if current_part:
                        chunk = ' '.join(current_part).strip() + "."
                        chunks.append(chunk)
                    current_part = [part + delimiter]
                    current_length = len(part) + 1
                else:
                    current_part.append(part + delimiter)
                    current_length += len(part) + len(delimiter) + 1
            
            # Add any remaining parts
            if current_part:
                chunk = ' '.join(current_part).strip()
                if not chunk.endswith(('.', '!', '?')):
                    chunk += "."
                chunks.append(chunk)
        else:
            chunks.append(sentence)
    
    # Final pass to ensure no chunk exceeds the limit
    final_chunks = []
    for chunk in chunks:
        if len(chunk) > max_chars:
            # Split into words and rebuild chunks
            words = chunk.split()
            current_chunk = []
            current_length = 0
            
            for word in words:
                if current_length + len(word) + 1 > max_chars:
                    if current_chunk:
                        text = ' '.join(current_chunk)
                        if not text.endswith(('.', '!', '?')):
                            text += "."
                        final_chunks.append(text)
                    current_chunk = [word]
                    current_length = len(word)
                else:
                    current_chunk.append(word)
                    current_length += len(word) + 1
            
            if current_chunk:
                text = ' '.join(current_chunk)
                if not text.endswith(('.', '!', '?')):
                    text += "."
                final_chunks.append(text)
        else:
            final_chunks.append(chunk)
    
    return final_chunks

def setup_google_credentials():
    """Set up Google Cloud credentials from environment variables."""
    credentials = {
        "type": "service_account",
        "project_id": os.getenv("GOOGLE_CLOUD_PROJECT_ID"),
        "private_key_id": os.getenv("GOOGLE_CLOUD_PRIVATE_KEY_ID"),
        "private_key": os.getenv("GOOGLE_CLOUD_PRIVATE_KEY", "").replace("\\n", "\n"),
        "client_email": os.getenv("GOOGLE_CLOUD_CLIENT_EMAIL"),
        "client_id": os.getenv("GOOGLE_CLOUD_CLIENT_ID"),
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
        "client_x509_cert_url": os.getenv("GOOGLE_CLOUD_CLIENT_X509_CERT_URL")
    }
    
    # Create temporary credentials file
    creds_path = "google_credentials_temp.json"
    with open(creds_path, "w") as f:
        json.dump(credentials, f)
    
    # Set environment variable for credentials
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = creds_path
    
    return creds_path

def get_max_chars_for_voice(voice: str) -> int:
    """Get the maximum characters allowed for a specific voice type."""
    if any(x in voice for x in ['Neural2', 'Chirp', 'News', 'Polyglot']):
        return 1000  # These models seem to handle longer text
    elif 'Standard' in voice:
        return 800  # More conservative limit for Standard voices
    else:
        return 500  # Most conservative limit for other voices

class TTSProvider(ABC):
    @abstractmethod
    async def convert_text(self, text: str, voice_id: str, output_path: Path) -> None:
        pass

class EdgeTTSProvider(TTSProvider):
    async def convert_text(self, text: str, voice_id: str, output_path: Path) -> None:
        try:
            communicate = edge_tts.Communicate(text, voice_id, rate="-10%", volume="+0%", pitch="+0Hz")
            async with aiofiles.open(output_path, mode="wb") as file:
                async for chunk in communicate.stream():
                    if chunk["type"] == "audio":
                        await file.write(chunk["data"])
        except Exception as e:
            raise Exception(f"EdgeTTS conversion failed: {str(e)}")

class GoogleTTSProvider(TTSProvider):
    def __init__(self):
        # Set up credentials
        self.creds_path = setup_google_credentials()
        try:
            self.client = texttospeech.TextToSpeechClient()
        except Exception as e:
            # Clean up credentials file if client initialization fails
            if os.path.exists(self.creds_path):
                os.remove(self.creds_path)
            raise e

    async def convert_text(self, text: str, voice_id: str, output_path: Path) -> None:
        try:
            # Get appropriate chunk size for this voice and preprocess text
            max_chars = get_max_chars_for_voice(voice_id)
            text_chunks = preprocess_text(text, max_chars=max_chars)
            
            # Create a temporary directory for chunk files
            temp_dir = Path(output_path).parent / "temp_chunks"
            os.makedirs(temp_dir, exist_ok=True)
            
            combined = AudioSegment.empty()
            
            # Process each chunk
            for i, chunk in enumerate(text_chunks):
                temp_chunk_path = temp_dir / f"chunk_{i}.mp3"
                
                # Configure input
                synthesis_input = texttospeech.SynthesisInput(text=chunk)

                # Build voice params
                voice_params = texttospeech.VoiceSelectionParams(
                    language_code=voice_id[:5],  # e.g., "en-US"
                    name=voice_id  # e.g., "en-US-Standard-A"
                )

                # Select audio config
                audio_config = texttospeech.AudioConfig(
                    audio_encoding=texttospeech.AudioEncoding.MP3
                )

                # Perform TTS request
                response = self.client.synthesize_speech(
                    input=synthesis_input,
                    voice=voice_params,
                    audio_config=audio_config
                )

                # Write chunk to temporary file
                with open(temp_chunk_path, "wb") as out:
                    out.write(response.audio_content)
                
                # Add to combined audio
                chunk_audio = AudioSegment.from_mp3(temp_chunk_path)
                combined += chunk_audio
                
                # Clean up chunk file
                os.remove(temp_chunk_path)
            
            # Export final combined audio
            combined.export(output_path, format="mp3")
            
            # Clean up temp directory
            os.rmdir(temp_dir)

        except Exception as e:
            # Clean up temp directory if it exists
            if os.path.exists(temp_dir):
                import shutil
                shutil.rmtree(temp_dir)
            raise Exception(f"Google TTS conversion failed: {str(e)}")
        finally:
            # Clean up credentials file
            if os.path.exists(self.creds_path):
                os.remove(self.creds_path)

    def __del__(self):
        # Ensure credentials file is cleaned up
        if hasattr(self, 'creds_path') and os.path.exists(self.creds_path):
            os.remove(self.creds_path)

class TTSService:
    def __init__(self):
        self._providers = {
            "edge": EdgeTTSProvider(),
            "google": GoogleTTSProvider()
        }

    async def convert_to_audio(self, text: str, voice_id: str, output_path: Path) -> None:
        """
        Convert text to audio using the appropriate provider.
        
        Args:
            text: The text to convert
            voice_id: The voice ID to use
            output_path: Where to save the audio file
        """
        # Determine provider from voice_id format
        if voice_id.endswith("Neural"):
            provider = "edge"
        else:
            provider = "google"
            
        await self._providers[provider].convert_text(text, voice_id, output_path)

    async def get_available_voices(self):
        """Get all available voices from both providers."""
        voices = []
        
        # Get Edge voices
        pattern = re.compile(r'en-(AU|GB|US)-\w+Neural$')
        for voice in edge_tts.list_voices():
            voice_id = voice["ShortName"]
            if pattern.match(voice_id):
                voices.append(voice_id)
        
        # Get Google voices
        try:
            google_provider = GoogleTTSProvider()
            response = google_provider.client.list_voices()
            pattern = re.compile(r'en-(AU|GB|US)-\w+')
            
            for voice in response.voices:
                for language_code in voice.language_codes:
                    if pattern.match(voice.name):
                        voices.append(voice.name)
                        break
        except Exception as e:
            print(f"Error getting Google voices: {str(e)}")
        
        return voices