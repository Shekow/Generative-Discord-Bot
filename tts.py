import os
import discord
import time
import pyttsx3 
from threading import Thread

tts_engine = pyttsx3.init()
tts_engine.setProperty('rate', 200)
tts_engine.setProperty('volume', 1)

class TTSVoiceQueue:
    def __init__(self, voice_client: discord.VoiceClient):
        self.queue = []
        self.guild_id = voice_client.guild.id
        self.voice_client = voice_client
        self.running = False

    def __len__(self) -> int:
        return len(self.queue)
    
    def __del__(self):
        self.clear()

    def _remove_file(self) -> None:
        try:
            os.remove(self._get_file_name())
        except Exception:
            pass

    def _get_file_name(self) -> str:
        return f"tts_{self.guild_id}.mp3"        

    def _keep_aive(self) -> None:
        try:
            while self.running:
                if not self.is_playing() and len(self) > 0:
                    self.play_next()
                time.sleep(1)

        except Exception as e:
            print(f"Keep alive failed for {self.guild_id} ({e})")

    def enqueue(self, text: str) -> None:
        self.queue.append(text)

    def dequeue(self) -> discord.AudioSource:
        if len(self) == 0:
            return None
        text = self.queue.pop(0)
        file_name = self._get_file_name()
        tts_engine.save_to_file(text, file_name)
        tts_engine.runAndWait()

        source = discord.FFmpegPCMAudio(source=file_name, executable="ffmpeg")
        return source
    
    def is_playing(self) -> bool:
        return self.voice_client.is_playing()

    def is_running(self) -> bool:
        return self.running

    def play_next(self) -> None:
        if self.is_playing() or len(self) == 0:
            return
        try:
            self.voice_client.play(source=self.dequeue(), after= lambda e=None: self._remove_file())
        except Exception as e:
            print(e)
            os.remove(self._get_file_name())

    def start(self) -> None:
        thread = Thread(target=self._keep_aive)
        thread.daemon = True
        self.running = True
        thread.start()
    
    def clear(self) -> None:
        self.running = False
        self.queue.clear()
        self._remove_file()