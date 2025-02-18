from abc import ABC, abstractmethod
import edge_tts
import asyncio
import aiofiles
from pathlib import Path
from google.cloud import texttospeech

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
        self.client = texttospeech.TextToSpeechClient()

    async def convert_text(self, text: str, voice_id: str, output_path: Path) -> None:
        try:
            # Configure input
            synthesis_input = texttospeech.SynthesisInput(text=text)

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

            # Write response to file
            with open(output_path, "wb") as out:
                out.write(response.audio_content)

        except Exception as e:
            raise Exception(f"Google TTS conversion failed: {str(e)}")

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