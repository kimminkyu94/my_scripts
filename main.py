from fastapi import FastAPI, BackgroundTasks, HTTPException
from pydantic import BaseModel
import subprocess
import requests
import os
import openai
import logging
import time
from dotenv import load_dotenv
import whisper

load_dotenv()

app = FastAPI()

logging.basicConfig(level=logging.DEBUG)

AIRTABLE_TOKEN = os.getenv('AIRTABLE_TOKEN')
BASE_ID = os.getenv('BASE_ID')
TABLE_NAME = os.getenv('TABLE_NAME')
FFMPEG_PATH = os.getenv('FFMPEG_PATH')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

openai.api_key = OPENAI_API_KEY

model = whisper.load_model("base")

class AutomationRequest(BaseModel):
    action: str
    record_id: str
    video_url: str = None
    lang: str = None
    title: str = None
    background_url: str = None
    country: str = None

def download_file(url, local_filename):
    local_path = os.path.abspath(local_filename)
    logging.debug(f"Downloading file from {url} to {local_path}")
    with requests.get(url, stream=True) as r:
        r.raise_for_status()
        with open(local_path, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
    logging.debug(f"Downloaded file saved to {local_path}")
    return local_path

def generate_subtitles(input_video_path, output_subtitles_path):
    logging.debug(f"Generating subtitles for {input_video_path}")
    result = model.transcribe(input_video_path)
    with open(output_subtitles_path, 'w', encoding='utf-8') as f:
        for segment in result['segments']:
            f.write(f"{segment['start']:.3f} --> {segment['end']:.3f}\n{segment['text']}\n\n")
    logging.debug(f"Subtitles generated at {output_subtitles_path}")

def translate_subtitles(subtitles_path, target_language):
    logging.debug(f"Translating subtitles from {subtitles_path} to {target_language}")
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
    logging.debug(f"Translated subtitles saved to {translated_subtitles_path}")

    return translated_subtitles_path

def translate_text(text, target_language):
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": f"Translate the following text to {target_language}:"},
                {"role": "user", "content": text}
            ]
        )
        translated_text = response.choices[0].message['content']
        logging.debug(f"Translated text: {translated_text}")
        return translated_text
    except openai.error.RateLimitError:
        logging.error("Rate limit exceeded. Retrying after a short delay.")
        time.sleep(60)
        return translate_text(text, target_language)

def merge_video_and_subtitles(input_video_path, subtitles_path, output_video_path, title, country_code):
    command = [
        FFMPEG_PATH, '-i', input_video_path, '-vf', f"subtitles={subtitles_path}:force_style='FontName=Arial,FontSize=24,PrimaryColour=&HFFFFFF&',drawtext=text='{title}':fontcolor=white:fontsize=48:x=(w-text_w)/2:y=50:box=1:boxcolor=black@0.5'", '-c:a', 'copy', '-y', output_video_path
    ]
    try:
        logging.debug(f"Running command: {' '.join(command)}")
        subprocess.run(command, check=True)
        logging.debug(f"Merged video saved to {output_video_path}")
    except subprocess.CalledProcessError as e:
        logging.error(f"Error occurred while running command: {e}")
        raise

def update_airtable_record(record_id, field_name, field_value):
    url = f"https://api.airtable.com/v0/{BASE_ID}/{TABLE_NAME}/{record_id}"
    headers = {
        "Authorization": f"Bearer {AIRTABLE_TOKEN}",
        "Content-Type": "application/json"
    }
    data = {
        "fields": {
            field_name: field_value
        }
    }
    logging.debug(f"Updating Airtable record {record_id} with {field_name}: {field_value}")
    response = requests.patch(url, headers=headers, json=data)
    response.raise_for_status()
    logging.debug(f"Updated Airtable record {record_id}")

@app.post("/automate/")
async def automate(request: AutomationRequest, background_tasks: BackgroundTasks):
    if request.action == "create_subtitles":
        background_tasks.add_task(create_subtitles_task, request)
    elif request.action == "create_videos":
        background_tasks.add_task(create_videos_task, request)
    else:
        raise HTTPException(status_code=400, detail="Invalid action")
    return {"status": "Task started"}

def create_subtitles_task(request: AutomationRequest):
    video_path = download_file(request.video_url, f"{request.record_id}.mp4")
    subtitles_path = f"{request.record_id}.srt"
    generate_subtitles(video_path, subtitles_path)
    translated_subtitles_path = translate_subtitles(subtitles_path, request.lang)
    update_airtable_record(request.record_id, "translated_subtitles", translated_subtitles_path)

def create_videos_task(request: AutomationRequest):
    video_path = download_file(request.video_url, 'original_video.mp4')
    background_path = download_file(request.background_url, 'background.jpg')
    subtitles_path = 'subtitles.srt'
    generate_subtitles(video_path, subtitles_path)
    translated_subtitles_path = translate_subtitles(subtitles_path, request.country)
    output_video_path = 'output_video.mp4'
    merge_video_and_subtitles(video_path, translated_subtitles_path, output_video_path, request.title, request.country)
    youtube_url = 'https://youtube.com/dummy_url'
    update_airtable_record(request.record_id, 'youtube1', youtube_url)
    logging.debug("Video processing completed")


