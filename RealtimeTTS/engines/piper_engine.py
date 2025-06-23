import os
import wave
import tempfile
import pyaudio
import subprocess
from typing import Optional
from .base_engine import BaseEngine
from queue import Queue
import json

class PiperVoice:
    def __init__(self, model_file: str, config_file: Optional[str] = None):
        self.model_file = model_file
        if config_file is None:
            possible_json = f"{model_file}.json"
            self.config_file = possible_json if os.path.isfile(possible_json) else None
        else:
            self.config_file = config_file

        self.native_sample_rate = 24000
        if self.config_file and os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
                    if 'audio' in config_data and 'sample_rate' in config_data['audio']:
                        self.native_sample_rate = int(config_data['audio']['sample_rate'])
                    elif 'sample_rate' in config_data:
                        self.native_sample_rate = int(config_data['sample_rate'])
            except Exception:
                pass

    def __repr__(self):
        return (
            f"PiperVoice(model_file='{self.model_file}', "
            f"config_file='{self.config_file}', native_sample_rate={self.native_sample_rate})"
        )

class PiperEngine(BaseEngine):
    def __init__(self,
                 piper_path: Optional[str] = None,
                 voice: Optional[PiperVoice] = None,
                 length_scale: float = 1.0):
        if piper_path is None:
            env_path = os.environ.get("PIPER_PATH")
            default_exe = "piper.exe" if os.name == 'nt' else "piper"
            self.piper_path = env_path if env_path else default_exe
        else:
            self.piper_path = piper_path

        self.voice = voice
        self.length_scale = length_scale
        self.queue = Queue()


    def get_stream_info(self):
        rate = 24000
        if self.voice and hasattr(self.voice, 'native_sample_rate'):
            rate = self.voice.native_sample_rate
        return pyaudio.paInt16, 1, 24000

    def synthesize(self, text: str) -> bool:
        if not self.voice or not self.voice.model_file:
            print("Error: PiperEngine - Voice model not set.")
            return False

        output_wav_path = ""
        try:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_wav_file:
                output_wav_path = tmp_wav_file.name

            cmd_list = [
                self.piper_path,
                "-m", self.voice.model_file,
                "-f", output_wav_path
            ]

            if self.voice.config_file and os.path.exists(self.voice.config_file):
                cmd_list.extend(["-c", self.voice.config_file])

            if self.length_scale != 1.0:
                cmd_list.extend(["--length_scale", str(self.length_scale)])

            result = subprocess.run(
                cmd_list,
                input=text.encode("utf-8"),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
                shell=False
            )

            with wave.open(output_wav_path, "rb") as wf:
                audio_data = wf.readframes(wf.getnframes())
                self.queue.put(audio_data)
            return True

        except FileNotFoundError:
            print(f"Error: Piper executable not found at '{self.piper_path}'.")
            return False
        except subprocess.CalledProcessError as e:
            print(f"Error running Piper (exit code {e.returncode}): {e.stderr.decode('utf-8', errors='replace')}")
            return False
        except wave.Error as e:
            print(f"Error processing WAV file {output_wav_path}: {e}")
            return False
        except Exception as e:
            print(f"Unexpected error in PiperEngine.synthesize: {e}")
            return False
        finally:
            if output_wav_path and os.path.isfile(output_wav_path):
                try:
                    os.remove(output_wav_path)
                except Exception:
                    pass

    def set_voice(self, voice: PiperVoice):
        self.voice = voice

    def get_voices(self):
        return []