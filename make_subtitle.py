import os
import json
import requests
from google.cloud import storage
from google.auth.transport import requests as auth_requests
from google.oauth2 import id_token

# Initialize Google Cloud Storage client
storage_client = storage.Client()
bucket_name = 'allcloudvideo'  # Replace with your bucket name
video_file_path = 'videos/original_video.mp4'

# URL of the Cloud Run service (subtitle-service)
subtitle_service_url = 'https://subtitle-service-url/automate/'  # Replace with your Cloud Run URL

# Function to get the signed URL for the video file in the bucket
def get_signed_url(bucket_name, blob_name, expiration=3600):
    """Generate a signed URL for the blob"""
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    return blob.generate_signed_url(expiration=expiration)

# Function to trigger the subtitle-service
def trigger_subtitle_service(request):
    # Generate a signed URL for the video file
    video_url = get_signed_url(bucket_name, video_file_path)

    # Prepare the request payload
    payload = {
        "action": "create_subtitles",
        "video_url": video_url,
        "country": "en"  # Replace with the desired target language or country
    }

    # Get the authentication token for the Cloud Run service
    auth_token = id_token.fetch_id_token(auth_requests.Request(), subtitle_service_url)

    # Send the request to the subtitle-service
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {auth_token}"
    }

    response = requests.post(subtitle_service_url, headers=headers, data=json.dumps(payload))

    # Check response status
    if response.status_code == 200:
        return f"Request successfully sent to subtitle-service: {response.json()}"
    else:
        return f"Failed to send request to subtitle-service: {response.status_code} {response.text}"

# This function will be triggered by an HTTP request
def make_subtitle(request):
    return trigger_subtitle_service(request)
