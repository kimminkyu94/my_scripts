import os
import json
from google.cloud import storage
from flask import Flask, jsonify, request
import traceback
import logging
import requests

# Initialize Flask app
app = Flask(__name__)

# Initialize Google Cloud Storage client
storage_client = storage.Client()
output_bucket_name = 'allcloudstorage2'  # Output bucket for storing subtitles

# Configure logging
logging.basicConfig(level=logging.INFO)

@app.route('/automate', methods=['POST'])
def handle_subtitle_request():
    logging.info("Received request for subtitle creation.")
    logging.info("Raw request data: %s", request.data)

    # Parse the incoming request data
    try:
        data = request.get_json(silent=True)
        if not data:
            logging.error("Error: No data received or invalid JSON.")
            return jsonify({'error': 'Invalid or missing payload'}), 400
        logging.info("Parsed JSON data: %s", data)
    except Exception as e:
        logging.error("Error parsing JSON: %s", e)
        return jsonify({'error': 'Error parsing payload'}), 400

    # Validate the payload
    action = data.get('action')
    video_url = data.get('video_url')
    if action != 'create_subtitles' or not video_url:
        logging.error("Error: Missing or invalid fields - Action: %s, Video URL: %s", action, video_url)
        return jsonify({'error': 'Missing or invalid required fields: action, video_url'}), 400

    try:
        # Validate the video URL and format
        if not validate_video_url(video_url):
            logging.error("Error: Unsupported video format or inaccessible file at URL: %s", video_url)
            return jsonify({'error': 'Unsupported video format or inaccessible file'}), 422
        
        # Extract and translate subtitles
        subtitles = extract_and_translate_subtitles(video_url)
        if not subtitles:
            logging.error("Error: No subtitles generated.")
            return jsonify({'error': 'Subtitle extraction failed'}), 422

        # Extract video name from URL
        video_name = os.path.splitext(os.path.basename(video_url))[0]
        save_subtitles(subtitles, video_name)
    except FileNotFoundError:
        logging.error("Error: File not found at URL: %s", video_url)
        return jsonify({'error': 'File not found'}), 422
    except UnsupportedFormatError:
        logging.error("Error: Unsupported video format for URL: %s", video_url)
        return jsonify({'error': 'Unsupported video format'}), 422
    except Exception as e:
        logging.error("Unexpected error during subtitle extraction: %s", e)
        logging.error("Stack trace: %s", traceback.format_exc())
        return jsonify({'error': 'Internal server error'}), 500

    return jsonify({'message': 'Subtitles created and saved successfully'}), 200

def validate_video_url(video_url):
    logging.info("Validating video URL: %s", video_url)
    try:
        response = requests.head(video_url)
        content_type = response.headers.get('Content-Type', '')
        if 'video' in content_type:
            logging.info("Valid video content type: %content_type", content_type)
            return True
        else:
            logging.error("Invalid content type: %s", content_type)
            return False
    except requests.RequestException as e:
        logging.error("Error accessing the URL: %s", e)
        return False

def extract_and_translate_subtitles(video_url):
    logging.info("Attempting to extract subtitles from video URL: %s", video_url)
    try:
        # Placeholder for actual Whisper processing logic
        subtitles = {
            "America": "Sample subtitle content",
            # Real logic will generate actual subtitles here
        }
        logging.info("Subtitles extraction succeeded. Languages: %s", list(subtitles.keys()))
        return subtitles
    except Exception as e:
        logging.error("Error during subtitle extraction: %s", e)
        logging.error("Stack trace: %s", traceback.format_exc())
        raise

def save_subtitles(subtitles, video_name):
    logging.info("Saving subtitles for video: %s", video_name)
    for country, subtitle_content in subtitles.items():
        folder_name = f"sub/{country}"
        file_name = f"{video_name}_{country}.srt"
        destination_blob_name = f"{folder_name}/{file_name}"
        
        try:
            bucket = storage_client.bucket(output_bucket_name)
            blob = bucket.blob(destination_blob_name)
            blob.upload_from_string(subtitle_content)
            logging.info("Saved subtitle for %s at %s", country, destination_blob_name)
        except Exception as e:
            logging.error("Error saving subtitle for %s: %s", country, e)
            logging.error("Stack trace: %s", traceback.format_exc())
            raise

# Start the Flask app
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
