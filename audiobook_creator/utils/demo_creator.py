import asyncio
import os
import edge_tts
import aiofiles
from pathlib import Path
import argparse
from google.cloud import texttospeech
import re
import json
from dotenv import load_dotenv
import nltk
from io import BytesIO
from pydub import AudioSegment

# Load environment variables
load_dotenv()

# Download required NLTK data
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt')

def preprocess_text(text: str, max_chars: int = 1000, provider: str = "edge") -> list[str]:
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
    
    # Verify no chunk exceeds the limit
    for chunk in final_chunks:
        if len(chunk) > max_chars:
            raise ValueError(f"Chunk exceeds limit ({len(chunk)} > {max_chars}): {chunk[:100]}...")
    
    return final_chunks

class TTSProvider:
    async def text_to_speech(self, text: str, voice: str, output_file: str):
        raise NotImplementedError

class EdgeTTSProvider(TTSProvider):
    async def text_to_speech(self, text: str, voice: str, output_file: str):
        try:
            communicate = edge_tts.Communicate(text, voice, rate="-10%", volume="+0%", pitch="+0Hz")
            async with aiofiles.open(output_file, mode="wb") as file:
                async for chunk in communicate.stream():
                    if chunk["type"] == "audio":
                        await file.write(chunk["data"])
            print(f"Successfully created audio file: {output_file}")
        except Exception as e:
            print(f"Error converting text to speech: {str(e)}")
            raise

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

    async def text_to_speech(self, text: str, voice: str, output_file: str):
        try:
            # Get appropriate chunk size for this voice
            max_chars = get_max_chars_for_voice(voice)
            print(f"Using max chunk size of {max_chars} characters for voice {voice}")
            
            # Split text into manageable chunks
            text_chunks = preprocess_text(text, max_chars=max_chars, provider="google")
            print(f"Split text into {len(text_chunks)} chunks")
            
            # Process each chunk and write to file
            with open(output_file, "wb") as out_file:
                for i, chunk in enumerate(text_chunks, 1):
                    try:
                        print(f"Processing chunk {i}/{len(text_chunks)} for {voice} (length: {len(chunk)} chars)")
                        
                        # Configure input
                        synthesis_input = texttospeech.SynthesisInput(text=chunk)

                        # Build voice params
                        voice_params = texttospeech.VoiceSelectionParams(
                            language_code=voice[:5],  # e.g., "en-US"
                            name=voice  # e.g., "en-US-Standard-A"
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

                        # Write audio content directly to file
                        out_file.write(response.audio_content)
                        
                    except Exception as e:
                        print(f"Error processing chunk {i} for voice {voice}:")
                        print(f"Chunk text: {chunk}")
                        print(f"Error details: {str(e)}")
                        raise

            print(f"Successfully created audio file: {output_file}")
            
        except Exception as e:
            print(f"Error converting text to speech: {str(e)}")
            raise
        finally:
            # Clean up credentials file
            if os.path.exists(self.creds_path):
                os.remove(self.creds_path)

def get_edge_voices():
    """Get all English voices from Edge TTS for specified regions."""
    voices = []
    # Edge TTS voice pattern
    pattern = re.compile(r'en-(AU|GB|US)-\w+Neural$')
    
    # Get all voices from edge-tts
    for voice in edge_tts.list_voices():
        voice_id = voice["ShortName"]
        if pattern.match(voice_id):
            voices.append(voice_id)
    
    return voices

async def get_google_voices():
    """Get all English voices from Google Cloud TTS for specified regions."""
    voices = []
    creds_path = setup_google_credentials()
    
    try:
        # Initialize client with credentials
        client = texttospeech.TextToSpeechClient()
        
        # List available voices
        response = client.list_voices()
        pattern = re.compile(r'en-(AU|GB|US)-\w+')
        
        for voice in response.voices:
            # Check if voice is for English and from desired regions
            for language_code in voice.language_codes:
                if pattern.match(voice.name):
                    voices.append(voice.name)
                    break
    finally:
        # Clean up temporary credentials file
        if os.path.exists(creds_path):
            os.remove(creds_path)
    
    return voices

async def text_to_speech(input_file: str, output_dir: str, provider: str, voice: str):
    """Convert text file to speech using specified provider."""
    
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    output_file = os.path.join(output_dir, f"{voice}.mp3")
    
    # Skip if file already exists
    if os.path.exists(output_file):
        print(f"Skipping {voice} - output file already exists")
        return
    
    # Read input text
    with open(input_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Create provider instance
    if provider.lower() == "edge":
        tts_provider = EdgeTTSProvider()
    elif provider.lower() == "google":
        tts_provider = GoogleTTSProvider()
    else:
        raise ValueError(f"Unsupported provider: {provider}")
    
    await tts_provider.text_to_speech(content, voice, output_file)

async def main():
    parser = argparse.ArgumentParser(description='Convert text file to speech')
    parser.add_argument('input_file', help='Path to input text file')
    parser.add_argument('--output-dir', default='output', help='Directory for output audio file')
    parser.add_argument('--provider', choices=['edge', 'google'], default='edge', help='TTS provider to use')
    
    args = parser.parse_args()
    
    # Get voices based on provider
    if args.provider == 'edge':
        voices = get_edge_voices()
    else:  # google
        voices = await get_google_voices()
    
    print(f"Found {len(voices)} voices for provider {args.provider}")
    
    for voice in voices:
        await text_to_speech(args.input_file, args.output_dir, args.provider, voice)

if __name__ == "__main__":
    asyncio.run(main())