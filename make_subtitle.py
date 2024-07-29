import os
import json
from google.cloud import storage
from flask import Flask, jsonify, request
import traceback

# Initialize Flask app
app = Flask(__name__)

# Initialize Google Cloud Storage client
storage_client = storage.Client()
output_bucket_name = 'allcloudstorage2'  # Output bucket for storing subtitles

@app.route('/automate', methods=['POST'])
def handle_subtitle_request():
    print("Received request for subtitle creation.")
    print("Raw request data:", request.data)

    # Parse the incoming request data
    try:
        data = request.get_json(silent=True)
        if not data:
            print("Error: No data received or invalid JSON.")
            return jsonify({'error': 'Invalid or missing payload'}), 400
        print("Parsed JSON data:", data)
    except Exception as e:
        print(f"Error parsing JSON: {e}")
        return jsonify({'error': 'Error parsing payload'}), 400

    # Validate the payload
    action = data.get('action')
    video_url = data.get('video_url')
    if action != 'create_subtitles' or not video_url:
        print(f"Error: Missing or invalid fields - Action: {action}, Video URL: {video_url}")
        return jsonify({'error': 'Missing or invalid required fields: action, video_url'}), 400

    try:
        # Validate the video URL and format
        if not validate_video_url(video_url):
            print(f"Error: Unsupported video format or inaccessible file at URL: {video_url}")
            return jsonify({'error': 'Unsupported video format or inaccessible file'}), 422
        
        # Extract and translate subtitles
        subtitles = extract_and_translate_subtitles(video_url)
        if not subtitles:
            print("Error: No subtitles generated.")
            return jsonify({'error': 'Subtitle extraction failed'}), 422

        # Extract video name from URL
        video_name = os.path.splitext(os.path.basename(video_url))[0]
        save_subtitles(subtitles, video_name)
    except FileNotFoundError:
        print(f"Error: File not found at URL: {video_url}")
        return jsonify({'error': 'File not found'}), 422
    except UnsupportedFormatError:
        print(f"Error: Unsupported video format for URL: {video_url}")
        return jsonify({'error': 'Unsupported video format'}), 422
    except Exception as e:
        print(f"Unexpected error during subtitle extraction: {e}")
        print("Stack trace:", traceback.format_exc())
        return jsonify({'error': 'Internal server error'}), 500

    return jsonify({'message': 'Subtitles created and saved successfully'}), 200

def validate_video_url(video_url):
    # Placeholder function to validate video URL and format
    # This function should check if the URL points to a valid file that is accessible
    # and whether the file format is supported
    print(f"Validating video URL: {video_url}")
    # Implement actual validation logic here
    return True

def extract_and_translate_subtitles(video_url):
    print(f"Attempting to extract subtitles from video URL: {video_url}")
    
    try:
        # Placeholder for actual Whisper processing logic
        subtitles = {
            "America": "Sample subtitle content",
            # Real logic will generate actual subtitles here
        }
        print(f"Subtitles extraction succeeded. Languages: {list(subtitles.keys())}")
        return subtitles
    except Exception as e:
        print(f"Error during subtitle extraction: {e}")
        print("Stack trace:", traceback.format_exc())
        raise

def save_subtitles(subtitles, video_name):
    print(f"Saving subtitles for video: {video_name}")
    for country, subtitle_content in subtitles.items():
        folder_name = f"sub/{country}"
        file_name = f"{video_name}_{country}.srt"
        destination_blob_name = f"{folder_name}/{file_name}"
        
        try:
            bucket = storage_client.bucket(output_bucket_name)
            blob = bucket.blob(destination_blob_name)
            blob.upload_from_string(subtitle_content)
            print(f"Saved subtitle for {country} at {destination_blob_name}")
        except Exception as e:
            print(f"Error saving subtitle for {country}: {e}")
            print("Stack trace:", traceback.format_exc())
            raise

# Start the Flask app
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
