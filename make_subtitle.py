import os
import openai
import logging
import requests
import traceback
from pyairtable import Table
from flask import Flask, request, jsonify

# 로깅 설정을 더 자세하게 구성
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

app = Flask(__name__)

# OpenAI API 키 설정
openai.api_key = os.getenv('OPENAI_API_KEY')
logging.info(f"OpenAI API Key Loaded: {bool(openai.api_key)}")

def validate_video_url(video_url):
    logging.debug(f"Validating video URL: {video_url}")
    try:
        response = requests.head(video_url)
        content_type = response.headers.get('Content-Type', '')
        logging.debug(f"Content-Type: {content_type}")
        if 'video' in content_type:
            logging.info(f"Valid video content type: {content_type}")
            return True
        else:
            logging.error(f"Invalid content type: {content_type}")
            return False
    except requests.RequestException as e:
        logging.error(f"Error accessing the URL: {str(e)}")
        return False

def download_audio_from_video(video_url, filename):
    logging.debug(f"Attempting to download audio from: {video_url}")
    try:
        response = requests.get(video_url, stream=True)
        if response.status_code == 200:
            with open(filename, 'wb') as f:
                for chunk in response.iter_content(1024):
                    f.write(chunk)
            logging.info(f"Downloaded file saved to: {filename}")
            return filename
        else:
            logging.error(f"Failed to download video/audio. Status code: {response.status_code}")
            return None
    except Exception as e:
        logging.error(f"Error during download: {str(e)}")
        return None

def transcribe_audio_with_whisper(audio_file_path):
    logging.debug(f"Attempting to transcribe audio file: {audio_file_path}")
    try:
        with open(audio_file_path, 'rb') as audio_file:
            response = openai.Audio.transcribe(
                model="whisper-1",
                file=audio_file,
                response_format='verbose_json',
                language='ko'
            )
            logging.debug(f"Whisper API response: {response}")
            segments = response.get('segments', [])
            for segment in segments:
                original_text = segment['text']
                decoded_text = original_text.encode('utf-8').decode('unicode_escape')
                segment['text'] = decoded_text
                logging.debug(f"Segment - Original: {original_text}, Decoded: {decoded_text}")
            return segments
    except Exception as e:
        logging.error(f"Error during transcription: {str(e)}")
        logging.error(f"Stack trace: {traceback.format_exc()}")
        return []

def format_to_srt(segments):
    logging.debug("Formatting transcription to SRT")
    subtitles = []
    for i, segment in enumerate(segments, 1):
        start_time = segment['start']
        end_time = segment['end']
        text = segment['text'].strip()
        subtitles.append(f"{i}\n{convert_time(start_time)} --> {convert_time(end_time)}\n{text}")
    
    formatted_srt = "\n\n".join(subtitles)
    logging.debug(f"Formatted SRT (first 500 chars): {formatted_srt[:500]}...")
    return formatted_srt

def convert_time(seconds):
    ms = int((seconds % 1) * 1000)
    s = int(seconds)
    hrs = s // 3600
    mins = (s % 3600) // 60
    secs = s % 60
    return f"{hrs:02}:{mins:02}:{secs:02},{ms:03}"

def extract_subtitles(video_url):
    logging.info(f"Starting subtitle extraction for URL: {video_url}")
    audio_file_path = download_audio_from_video(video_url, "/tmp/downloaded_audio.wav")
    if not audio_file_path:
        logging.error("Failed to download audio file.")
        raise Exception("Failed to download audio file.")

    segments = transcribe_audio_with_whisper(audio_file_path)
    logging.debug(f"Transcription segments count: {len(segments)}")

    if not segments:
        logging.error("No subtitles generated.")
        raise Exception("No subtitles generated.")

    subtitles = format_to_srt(segments)
    logging.info("Subtitles extraction succeeded.")
    return subtitles

def update_airtable(record_id, subtitles):
    logging.info(f"Updating Airtable record: {record_id}")
    try:
        AIRTABLE_TOKEN = os.getenv('AIRTABLE_TOKEN')
        AIRTABLE_BASE_ID = os.getenv('AIRTABLE_BASE_ID')
        AIRTABLE_TABLE_NAME = os.getenv('AIRTABLE_TABLE_NAME')

        if not all([AIRTABLE_TOKEN, AIRTABLE_BASE_ID, AIRTABLE_TABLE_NAME]):
            logging.error("Missing Airtable environment variables")
            raise ValueError("Missing Airtable environment variables")

        table = Table(AIRTABLE_TOKEN, AIRTABLE_BASE_ID, AIRTABLE_TABLE_NAME)
        result = table.update(record_id, {'자막': subtitles, '자막 생성 상태': '완료'})
        logging.info(f"Airtable update result: {result}")
        logging.info(f"Airtable record {record_id} updated successfully")
    except Exception as e:
        logging.error(f"Error updating Airtable: {str(e)}")
        logging.error(f"Stack trace: {traceback.format_exc()}")
        raise

@app.route('/make_subtitle', methods=['POST'])
def handle_request():
    logging.info("Received request for subtitle generation")
    try:
        data = request.json
        logging.debug(f"Request data: {data}")

        video_url = data.get('videoUrl')
        record_id = data.get('record_id')

        if not video_url:
            logging.error("Video URL is missing")
            return jsonify({"error": "Video URL is missing"}), 400

        if not validate_video_url(video_url):
            logging.error("Invalid video URL")
            return jsonify({"error": "Invalid video URL"}), 400

        subtitles = extract_subtitles(video_url)
        update_airtable(record_id, subtitles)

        logging.info("Subtitle generation and Airtable update completed successfully")
        return jsonify({"message": "Subtitles generated and saved successfully", "subtitles": subtitles[:500] + "..."})
    except Exception as e:
        logging.error(f"Error in processing: {str(e)}")
        logging.error(f"Stack trace: {traceback.format_exc()}")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 8080))
    app.run(debug=True, host='0.0.0.0', port=port)
