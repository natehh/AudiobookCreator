import ssl
from pathlib import Path
from typing import List, Optional
import nltk
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup
import mobi
import shutil
import os
import re
import pyttsx3
import asyncio
import uuid
from datetime import datetime
from fastapi import FastAPI, UploadFile, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI()

def setup_nltk():
    try:
        _create_unverified_https_context = ssl._create_unverified_context
    except AttributeError:
        pass
    else:
        ssl._create_default_https_context = _create_unverified_https_context
    
    nltk.download('punkt', quiet=True)

def get_chapters(filepath: Path) -> List[tuple[str, str]]:
    suffix = filepath.suffix.lower()
    
    if suffix == '.epub':
        book = epub.read_epub(str(filepath))
        chapters = []
        
        for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
            soup = BeautifulSoup(item.content, 'html.parser')
            
            chapter_heads = soup.find_all(['h1', 'h2', 'h3'])
            
            if chapter_heads:
                for head in chapter_heads:
                    content = []
                    current = head.next_sibling
                    while current and not (isinstance(current, BeautifulSoup) and current.name in ['h1', 'h2', 'h3']):
                        if hasattr(current, 'get_text'):
                            text = current.get_text().strip()
                            if text:
                                content.append(text)
                        current = current.next_sibling
                    
                    chapter_text = ' '.join(content).strip()
                    if chapter_text:
                        chapters.append((
                            head.get_text().strip() or f"Chapter {len(chapters) + 1}",
                            chapter_text
                        ))
            else:
                text = soup.get_text().strip()
                if text:
                    chapters.append((
                        f"Chapter {len(chapters) + 1}",
                        text
                    ))
        
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
        text = filepath.read_text(encoding='utf-8')
        return [("Chapter 1", text)]

def get_book_title(filepath: Path) -> str:
   suffix = filepath.suffix.lower()
   
   if suffix == '.epub':
       book = epub.read_epub(str(filepath))
       return book.get_metadata('DC', 'title')[0][0].replace(" ", "_") or filepath.stem.replace(" ", "_")
   elif suffix == '.mobi':
       tempdir, mobipath = mobi.extract(str(filepath))
       try:
           return get_book_title(Path(mobipath)).replace(" ", "_")
       finally:
           shutil.rmtree(tempdir)
   else:
       return filepath.stem.replace(" ", "_")

class ConversionStatus(BaseModel):
    id: str
    status: str
    progress: float
    eta: Optional[str] = None
    output_files: List[str] = []
    error: Optional[str] = None
    temp_file: Optional[str] = None

class ConversionStore:
    def __init__(self):
        self.conversions: Dict[str, ConversionStatus] = {}
    
    def add(self, status: ConversionStatus):
        self.conversions[status.id] = status
    
    def get(self, conversion_id: str) -> Optional[ConversionStatus]:
        return self.conversions.get(conversion_id)
    
    def update(self, conversion_id: str, **kwargs):
        if conversion_id in self.conversions:
            current = self.conversions[conversion_id].model_dump()
            current.update(kwargs)
            self.conversions[conversion_id] = ConversionStatus(**current)

class AudiobookAPI:
    def __init__(self):
        self.app = FastAPI()
        self.store = ConversionStore()
        self.setup_routes()
    
    def setup_routes(self):
        @self.app.post("/convert/", response_model=ConversionStatus)
        async def create_conversion(
            background_tasks: BackgroundTasks,
            file: UploadFile,
            output_dir: str = "output"
        ):
            if not file.filename.endswith(('.epub', '.mobi', '.txt')):
                raise HTTPException(400, "Unsupported file format")
            
            temp_path = f"temp_{uuid.uuid4()}{os.path.splitext(file.filename)[1]}"
            with open(temp_path, "wb") as f:
                f.write(await file.read())
            
            converter = AudiobookConverter(temp_path, output_dir, self.store)
            
            status = ConversionStatus(
                id=converter.conversion_id,
                status="processing",
                progress=0.0,
                temp_file=temp_path
            )
            self.store.add(status)
            
            background_tasks.add_task(converter.convert)
            
            return status

        @self.app.get("/status/{conversion_id}", response_model=ConversionStatus)
        async def get_status(conversion_id: str):
            status = self.store.get(conversion_id)
            if not status:
                raise HTTPException(404, "Conversion not found")
            return status

        @self.app.delete("/cleanup/{conversion_id}")
        async def cleanup_conversion(conversion_id: str):
            status = self.store.get(conversion_id)
            if not status:
                raise HTTPException(404, "Conversion not found")
            
            if status.temp_file and os.path.exists(status.temp_file):
                os.remove(status.temp_file)
            
            return {"message": "Cleanup completed"}

class AudiobookConverter:
    def __init__(self, file_path: str, output_dir: str, store: ConversionStore):
        self.file_path = file_path
        self.output_dir = output_dir
        self.store = store
        self.conversion_id = str(uuid.uuid4())
        
    async def cleanup(self):
        """Remove temporary uploaded file"""
        if os.path.exists(self.file_path):
            try:
                os.remove(self.file_path)
            except OSError as e:
                print(f"Error cleaning up {self.file_path}: {e}")
        
    async def convert(self):
        try:
            setup_nltk()
            book_title = get_book_title(Path(self.file_path))
            chapters = get_chapters(Path(self.file_path))
            
            book_dir = os.path.join(self.output_dir, re.sub(r'[<>:"/\\|?*]', '_', book_title))
            os.makedirs(book_dir, exist_ok=True)
            
            total_words = sum(len(content.split()) for _, content in chapters)
            processed_words = 0
            
            engine = pyttsx3.init()
            engine.say(".")  # TODO: remove when ttsx3 bug is fixed
            
            for i, (title, content) in enumerate(chapters, 1):
                safe_title = re.sub(r'[<>:"/\\|?*]', '_', title)
                output_file = os.path.join(book_dir, f"{i:02d}_{safe_title}.wav")
                
                engine.save_to_file(content, output_file)
                engine.runAndWait()
                
                processed_words += len(content.split())
                progress = (processed_words / total_words) * 100
                
                self.store.update(
                    self.conversion_id,
                    progress=progress,
                    output_files=[*self.store.get(self.conversion_id).output_files, output_file]
                )
                
                await asyncio.sleep(0) 
            
            engine.stop()
            self.store.update(self.conversion_id, status="completed")
            
        except Exception as e:
            self.store.update(
                self.conversion_id,
                status="failed",
                error=str(e)
            )
            raise
        finally:
            await self.cleanup()

api = AudiobookAPI()
app = api.app

@app.post("/convert/", response_model=ConversionStatus)
async def create_conversion(
    background_tasks: BackgroundTasks,
    file: UploadFile,
    output_dir: str = "output"
):
    conversions = {}
    if not file.filename.endswith(('.epub', '.mobi', '.txt')):
        raise HTTPException(400, "Unsupported file format")
    
    temp_path = f"temp_{uuid.uuid4()}{os.path.splitext(file.filename)[1]}"
    with open(temp_path, "wb") as f:
        f.write(await file.read())
    
    converter = AudiobookConverter(temp_path, output_dir)
    
    conversions[converter.conversion_id] = ConversionStatus(
        id=converter.conversion_id,
        status="processing",
        progress=0.0,
        temp_file=temp_path,
        eta=None
    )
    
    background_tasks.add_task(converter.convert)
    
    return conversions[converter.conversion_id]

@app.get("/status/{conversion_id}", response_model=ConversionStatus)
async def get_status(conversion_id: str):
    if conversion_id not in conversions:
        raise HTTPException(404, "Conversion not found")
    return conversions[conversion_id]

@app.delete("/cleanup/{conversion_id}")
async def cleanup_conversion(conversion_id: str):
    if conversion_id not in conversions:
        raise HTTPException(404, "Conversion not found")
    
    status = conversions[conversion_id]
    if status.temp_file and os.path.exists(status.temp_file):
        os.remove(status.temp_file)
    
    return {"message": "Cleanup completed"}