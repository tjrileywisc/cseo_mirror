
import whisper
import subprocess
import os
import textwrap

from datetime import time

class CaptionExtractor:

    @staticmethod
    def seconds_to_srt_timestamp(value):
        hr = int(value// 3600)
        minute = int((value - hr * 3600) // 60)
        second = int(value- hr * 3600 - minute * 60)
        microsecond = int(1E6*(value - hr * 3600 - minute * 60 - second))
        ts = time(hour=hr, minute=minute, second=second, microsecond=microsecond)

        return ts.strftime("%H:%M:%S,%f")

    @staticmethod
    def extract_audio(video_path):
        audio_path = video_path.rsplit(".")[0] + ".m4a"
        if os.path.exists(audio_path):
            print(f"{audio_path} already exists")
            return audio_path

        ret = subprocess.call(["ffmpeg", "-i", video_path, "-c:a", "copy", "-vn", "-dn", audio_path])
        if ret != 0:
            print(f"couldn't extract the audio from {video_path}")
            return
        
        return audio_path

    @staticmethod
    def extract_captions(video_path):
        """
        Uses OpenAI's Whisper to transcribe English
        audio, and writes captions in srt format.
        """
        
        audio_path = CaptionExtractor.extract_audio(video_path)
        if not audio_path:
            return
        
        model = whisper.load_model('base', download_root=".")
        result = model.transcribe(audio_path)
        
        captions_path = video_path.rsplit(".")[0] + ".srt"
        
        with open(captions_path, "w") as f:
            for seq in result['segments']:
                n = seq['id'] + 1

                t_start = CaptionExtractor.seconds_to_srt_timestamp(seq['start'])
                t_finish = CaptionExtractor.seconds_to_srt_timestamp(seq['end'])
                template = f"""
                {n}
                {t_start} --> {t_finish}
                {seq['text']}
                """
                f.write(textwrap.dedent(template))