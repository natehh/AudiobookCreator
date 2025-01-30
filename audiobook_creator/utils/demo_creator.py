import asyncio
import os
import edge_tts
import aiofiles
from pathlib import Path
import argparse

async def text_to_speech(input_file: str, output_dir: str, voice: str):
    """Convert text file to speech using edge-tts."""
    
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Read input text
    with open(input_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Generate output filename from input filename
    input_filename = Path(input_file).stem
    output_file = os.path.join(output_dir, f"{voice}.mp3")
    
    try:
        # Initialize edge-tts communicator
        communicate = edge_tts.Communicate(content, voice)
        
        # Write audio data to file
        async with aiofiles.open(output_file, mode="wb") as file:
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    await file.write(chunk["data"])
        
        print(f"Successfully created audio file: {output_file}")
        
    except Exception as e:
        print(f"Error converting text to speech: {str(e)}")
        raise

def main():
    parser = argparse.ArgumentParser(description='Convert text file to speech')
    parser.add_argument('input_file', help='Path to input text file')
    parser.add_argument('--output-dir', default='output', help='Directory for output audio file')
    
    args = parser.parse_args()
    
    voices = [
        "en-AU-NatashaNeural",
        "en-AU-WilliamNeural",
        "en-CA-ClaraNeural",
        "en-CA-LiamNeural",
        "en-GB-LibbyNeural",
        "en-GB-MaisieNeural",
        "en-GB-RyanNeural",
        "en-GB-SoniaNeural",
        "en-GB-ThomasNeural",
        "en-HK-SamNeural",
        "en-HK-YanNeural",
        "en-IE-ConnorNeural",
        "en-IE-EmilyNeural",
        "en-IN-NeerjaNeural",
        "en-IN-PrabhatNeural",
        "en-KE-AsiliaNeural",
        "en-KE-ChilembaNeural",
        "en-NG-AbeoNeural",
        "en-NG-EzinneNeural",
        "en-NZ-MitchellNeural",
        "en-NZ-MollyNeural",
        "en-PH-JamesNeural",
        "en-PH-RosaNeural",
        "en-SG-LunaNeural",
        "en-SG-WayneNeural",
        "en-TZ-ElimuNeural",
        "en-TZ-ImaniNeural",
        "en-US-AnaNeural",
        "en-US-AriaNeural",
        "en-US-ChristopherNeural",
        "en-US-EricNeural",
        "en-US-GuyNeural",
        "en-US-JennyNeural",
        "en-US-MichelleNeural",
        "en-US-RogerNeural",
        "en-US-SteffanNeural",
        "en-ZA-LeahNeural",
        "en-ZA-LukeNeural"
    ]

    for voice in voices:
        asyncio.run(text_to_speech(args.input_file, args.output_dir, voice))

if __name__ == "__main__":
    main()