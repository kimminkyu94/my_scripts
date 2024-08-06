import os
import openai
import logging
import requests
import traceback
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from google.cloud import storage

app = FastAPI()

# Configure logging
logging.basicConfig(level=logging.INFO)

# Set OpenAI API key from environment variable
openai.api_key = os.getenv('OPENAI_API_KEY')
logging.info(f"OpenAI API Key Loaded: {bool(openai.api_key)}")

class VideoUrl(BaseModel):
    videoUrl: str

@app.post("/process")
def process_video(video: VideoUrl):
    try:
        subtitles = extract_subtitles(video.videoUrl)
        save_to_cloud_storage(video.videoUrl, subtitles, script='make_subtitle.py')
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
    if response.status_code == 200:
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
                response_format='verbose_json',
                language='ko'
            )
            logging.info(f"API response: {response}")
            segments = response.get('segments', [])
            for segment in segments:
                original_text = segment['text']
                decoded_text = original_text.encode('utf-8').decode('unicode_escape')
                segment['text'] = decoded_text
                logging.info(f"Original text: {original_text}")
                logging.info(f"Decoded text: {decoded_text}")
            return segments
    except Exception as e:
        logging.error(f"Error during transcription: {e}")
        logging.error("Stack trace: %s", traceback.format_exc())
        return []

def format_to_srt(segments):
    subtitles = []
    subtitle_index = 1
    for segment in segments:
        start_time = segment['start']
        end_time = segment['end']
        text = segment['text'].strip()
        
        subtitles.append(f"{subtitle_index}\n{convert_time(start_time)} --> {convert_time(end_time)}\n{text}")
        subtitle_index += 1
    
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

def save_to_cloud_storage(video_url, subtitles, script):
    logging.info(f"Attempting to save subtitles to Cloud Storage")
    try:
        storage_client = storage.Client()
        bucket = storage_client.bucket('allcloudstorage2')
        blob = bucket.blob(f"{os.path.basename(video_url)}.srt")
        logging.debug(f"Blob path: {blob.name}")
        logging.debug(f"Subtitles before saving: {subtitles}")
        
        # UTF-8로 디코딩한 후 다시 인코딩
        decoded_subtitles = subtitles.encode('latin1').decode('utf-8')
        
        logging.debug(f"Subtitles after decoding: {decoded_subtitles[:100]}")  # 처음 100자만 로깅
        
        blob.upload_from_string(decoded_subtitles, content_type="text/plain; charset=utf-8")
        logging.info(f"Subtitles saved to Cloud Storage: {blob.name}")
    except Exception as e:
        logging.error(f"Error saving subtitles to Cloud Storage: {e}")
        logging.error("Stack trace: %s", traceback.format_exc())
        raise
