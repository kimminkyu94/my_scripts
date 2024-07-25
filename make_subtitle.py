import os
import whisper
import openai
import requests
import logging
from google.cloud import storage
from fastapi import FastAPI, BackgroundTasks
from pydantic import BaseModel

# Initialize FastAPI app
app = FastAPI()

# Load Whisper model
model = whisper.load_model("base")

# Set OpenAI API key (assume it's set in environment variables)
openai.api_key = os.getenv("OPENAI_API_KEY")

# Base path for storing subtitles locally
BASE_SUBTITLE_PATH = "country"  # Root directory for subtitle files

class AutomationRequest(BaseModel):
    action: str
    video_url: str
    country: str

def download_file(url, local_filename):
    response = requests.get(url, stream=True)
    response.raise_for_status()
    with open(local_filename, 'wb') as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
    logging.info(f"Downloaded file saved to {local_filename}")
    return local_filename

def generate_subtitles(input_video_path, output_subtitles_path):
    result = model.transcribe(input_video_path)
    with open(output_subtitles_path, 'w') as f:
        for segment in result['segments']:
            f.write(f"{segment['start']:.3f} --> {segment['end']:.3f}\n{segment['text']}\n\n")
    logging.info(f"Subtitles generated at {output_subtitles_path}")

def translate_subtitles(subtitles_path, target_language):
    with open(subtitles_path, 'r', encoding='utf-8') as file:
        subtitles = file.readlines()

    translated_subtitles = []
    for line in subtitles:
        if line.strip().isdigit() or "-->" in line:
            translated_subtitles.append(line)
        else:
            translated_line = translate_text(line, target_language)
            translated_subtitles.append(translated_line + "\n")

    translated_subtitles_path = subtitles_path.replace('.srt', f'_{target_language}.srt')
    with open(translated_subtitles_path, 'w', encoding='utf-8') as file:
        file.writelines(translated_subtitles)
    logging.info(f"Translated subtitles saved to {translated_subtitles_path}")

    return translated_subtitles_path

def translate_text(text, target_language):
    try:
        response = openai.Completion.create(
            model="text-davinci-003",
            prompt=f"Translate the following text to {target_language}:\n{text}",
            max_tokens=500
        )
        return response.choices[0].text.strip()
    except Exception as e:
        logging.error(f"Error translating text: {e}")
        return text

def upload_to_gcs(bucket_name, source_file_path, destination_blob_name):
    """Uploads a file to the Google Cloud Storage bucket."""
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(destination_blob_name)

    blob.upload_from_filename(source_file_path)
    logging.info(f"File {source_file_path} uploaded to {destination_blob_name}.")

@app.post("/automate/")
async def automate(request: AutomationRequest, background_tasks: BackgroundTasks):
    if request.action == "create_subtitles":
        background_tasks.add_task(create_subtitles_task, request)
    return {"status": "Task started"}

def create_subtitles_task(request: AutomationRequest):
    # Download video
    video_path = download_file(request.video_url, "video.mp4")

    # Set directory path for storing subtitles
    country_folder = os.path.join(BASE_SUBTITLE_PATH, request.country)
    os.makedirs(country_folder, exist_ok=True)

    # Generate and store subtitles locally
    subtitles_path = os.path.join(country_folder, "subtitles.srt")
    generate_subtitles(video_path, subtitles_path)

    # Translate subtitles
    translated_subtitles_path = translate_subtitles(subtitles_path, request.country)

    # Upload translated subtitles to Google Cloud Storage
    bucket_name = 'allcloudstorage2'
    destination_blob_name = f"country/{request.country}/subtitles_{request.country}.srt"
    upload_to_gcs(bucket_name, translated_subtitles_path, destination_blob_name)

    logging.info(f"Subtitles for {request.country} are uploaded to {bucket_name}")
