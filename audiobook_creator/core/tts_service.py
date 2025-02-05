from abc import ABC, abstractmethod
import edge_tts
import asyncio
import aiofiles
from pathlib import Path

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

class TTSService:
    def __init__(self):
        self._providers = {
            "edge": EdgeTTSProvider()
        }

    async def convert_to_audio(self, text: str, voice_id: str, output_path: Path) -> None:
        """
        Convert text to audio using the appropriate provider.
        
        Args:
            text: The text to convert
            voice_id: The voice ID to use
            output_path: Where to save the audio file
        """
        provider = "edge"
        await self._providers[provider].convert_text(text, voice_id, output_path)