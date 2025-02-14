from openai import OpenAI
from openpyxl import load_workbook
from langdetect import detect_langs, DetectorFactory, detect
import ahocorasick
import requests
import deepl
from enum import Enum
from typing import Dict, Tuple, List, Union
import time # for speed logging
from fastapi import HTTPException

DetectorFactory.seed = 0
class LANGUAGES(Enum):
    ENGLISH = "en"
    TAIWANESE = "tw"
    JAPANESE = "ja"
    GERMAN = "de"

class STT(object):
    def __init__(self, client:OpenAI, keywords:List[str]=None):
        self.client = client
        self.init_prompt = self._make_init_prompt(keywords)

    def transcript(self, audio_file) -> str:
        result = self.client.audio.transcriptions.create(
            model="whisper-1", 
            file=audio_file,
            prompt=self.init_prompt
        )
        # print(result)
        return result.text

    def transcript_by_path(self, audio_file_path) -> str:
        audio_file = open(audio_file_path, "rb")
        return self.transcript(audio_file)

    def _make_init_prompt(self, keywords: list[str]) -> str:
        if keywords:
            prompt = (
                "Recognize the following keywords accurately and emphasize them strongly: " + ", ".join(keywords) + ". "\
                +"If any Simplified Chinese is detected, please respond using Traditional Chinese. "\
                +"Whisper, Ok. "\
                +"A pertinent sentence for your purpose in your language. "\
                +"Ok, Whisper. Whisper, Ok. Ok, Whisper. Whisper, Ok. "\
                +"Please find here, an unlikely ordinary sentence. "\
                +"This is to avoid a repetition to be deleted. "\
                +"Ok, Whisper. "
            )
        else:
            prompt = (
                "If any Simplified Chinese is detected, please respond using Traditional Chinese. "\
                +"Whisper, Ok. "\
                +"A pertinent sentence for your purpose in your language. "\
                +"Ok, Whisper. Whisper, Ok. Ok, Whisper. Whisper, Ok. "\
                +"Please find here, an unlikely ordinary sentence. "\
                +"This is to avoid a repetition to be deleted. "\
                +"Ok, Whisper. "
            )
        return prompt
        # print(prompt)
    
    def accumulate_chunks(self, chunks):
        return b''.join(chunks)
    
    def transcript_by_chunk(self, audio_chunk: bytes) -> str:
        try:
            with open("complete_audio.wav", "rb") as f:
                result = self.client.audio.transcriptions.create(
                    model="whisper-1",
                    file=f,
                    prompt=self.init_prompt
                )
            return result.text
        except Exception as e:
            print(f"Transcription error: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error transcribing audio: {str(e)}")
        
class lang_detector(object):
    
    def __init__(self):
        pass

    def detect_language_text(self, text:str) -> str:
        detected = detect_langs(text)
        filtered = [lang for lang in detected if lang.lang in LANGUAGES]
        if filtered:
            result = max(filtered, key=lambda l: l.prob).lang
        else:
            result = LANGUAGES.ENGLISH.value
        return result