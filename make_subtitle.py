import openai
import logging
import requests
import os
import traceback
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI()

# Configure logging
logging.basicConfig(level=logging.INFO)

# Set OpenAI API key
openai.api_key = os.getenv('OPENAI_API_KEY')

class VideoUrl(BaseModel):
    videoUrl: str

@app.post("/process")
def process_video(video: VideoUrl):
    try:
        subtitles = extract_subtitles(video.videoUrl)
        return {"subtitles": subtitles}
    except Exception as e:
        logging.error(f"Error in processing: {e}")
        raise HTTPException(status_code=500, detail="Error processing video")

def validate_video_url(video_url):
    logging.info("Validating video URL: %s", video_url)
    try:
        response = requests.head(video_url)
        content_type = response.headers.get('Content-Type', '')
        if 'video' in content_type:
            logging.info("Valid video content type: %s", content_type)
            return True
        else:
            logging.error("Invalid content type: %s", content_type)
            return False
    except requests.RequestException as e:
        logging.error("Error accessing the URL: %s", e)
        return False

def download_audio_from_video(video_url, filename):
    logging.info("Downloading audio file from: %s", video_url)
    response = requests.get(video_url, stream=True)
    if response.status_code == 200):
        with open(filename, 'wb') as f:
            for chunk in response.iter_content(1024):
                f.write(chunk)
        logging.info("Downloaded file saved to: %s", filename)
        return filename
    else:
        logging.error("Failed to download video/audio. Status code: %s", response.status_code)
        return None

def transcribe_audio_with_whisper(audio_file_path):
    try:
        with open(audio_file_path, 'rb') as audio_file:
            response = openai.Audio.transcribe(
                model="whisper-1",
                file=audio_file,
                response_format='verbose_json'
            )
            logging.info(f"API response: {response}")
            return response.get('segments', [])
    except Exception as e:
        logging.error(f"Error during transcription: {e}")
        logging.error("Stack trace: %s", traceback.format_exc())
        return []

def format_to_srt(segments):
    subtitles = []
    for i, segment in enumerate(segments, start=1):
        start_time = convert_time(segment['start'])
        end_time = convert_time(segment['end'])
        text = segment['text'].strip()
        subtitles.append(f"{i}\n{start_time} --> {end_time}\n{text}")
    return "\n\n".join(subtitles)

def convert_time(seconds):
    ms = int((seconds % 1) * 1000)
    s = int(seconds)
    hrs = s // 3600
    mins = (s % 3600) // 60
    secs = s % 60
    return f"{hrs:02}:{mins:02}:{secs:02},{ms:03}"

def extract_subtitles(video_url):
    logging.info("Attempting to extract subtitles from URL: %s", video_url)
    audio_file_path = download_audio_from_video(video_url, "/tmp/downloaded_audio.wav")
    if not audio_file_path:
        raise Exception("Failed to download audio file.")

    segments = transcribe_audio_with_whisper(audio_file_path)
    logging.info(f"Segments: {segments}")

    if not segments:
        raise Exception("No subtitles generated.")

    subtitles = format_to_srt(segments)
    logging.info("Subtitles extraction succeeded.")
    return subtitles
