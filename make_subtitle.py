import os
import json
from google.cloud import storage
from flask import jsonify, request

# Initialize Google Cloud Storage client
storage_client = storage.Client()
output_bucket_name = 'allcloudstorage2'  # Output bucket for storing subtitles

def extract_and_translate_subtitles(video_url):
    """
    Extract and translate subtitles from the video.
    This function should implement the logic to extract subtitles using a tool like Whisper,
    and then translate those subtitles using an API like OpenAI.
    """
    # Placeholder implementation for demonstration
    subtitles = {
        "America": "English subtitles content",
        "Brazil": "Portuguese subtitles content",
        "Filipin": "Filipino subtitles content",
        "Indonesia": "Indonesian subtitles content",
        "Japan": "Japanese subtitles content",
        "Korea": "Korean subtitles content",
        "Malaysia": "Malay subtitles content",
        "Mexico": "Spanish subtitles content",
        "Thailand": "Thai subtitles content",
        "United_Kingdom": "British English subtitles content",
        "Vietnam": "Vietnamese subtitles content"
        # Add more languages as needed
    }
    return subtitles

def save_subtitles(subtitles, video_name):
    """
    Save the subtitles to Google Cloud Storage under the 'sub' folder.
    """
    for country, subtitle_content in subtitles.items():
        folder_name = f"sub/{country}"  # Folder path includes 'sub' and country
        file_name = f"{video_name}_{country}.srt"  # Subtitle file name, e.g., video_America.srt
        destination_blob_name = f"{folder_name}/{file_name}"
        
        # Upload the file to the output bucket
        bucket = storage_client.bucket(output_bucket_name)
        blob = bucket.blob(destination_blob_name)
        blob.upload_from_string(subtitle_content)
        print(f"Saved subtitle for {country} at {destination_blob_name}")

def handle_subtitle_request(request):
    # Parse the incoming request data
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'Invalid or missing payload'}), 400

    # Check for required fields in the payload
    action = data.get('action')
    video_url = data.get('video_url')

    if action != 'create_subtitles' or not video_url:
        return jsonify({'error': 'Missing or invalid required fields: action, video_url'}), 400

    # Extract and translate subtitles
    subtitles = extract_and_translate_subtitles(video_url)
    
    # Extract video name from URL (assuming the video URL contains the file name)
    video_name = os.path.splitext(os.path.basename(video_url))[0]

    # Save the subtitles
    save_subtitles(subtitles, video_name)

    return jsonify({'message': 'Subtitles created and saved successfully'}), 200

# This function will be triggered by an HTTP request
def make_subtitle(request):
    return handle_subtitle_request(request)

