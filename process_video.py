import os
import tempfile
from google.cloud import storage, pubsub_v1
import ffmpeg
import logging

# Set up logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

# Google Cloud Storage client setup
storage_client = storage.Client()

# Google Pub/Sub client setup
publisher = pubsub_v1.PublisherClient()
subscriber = pubsub_v1.SubscriberClient()

# Pub/Sub topic and subscription
TOPIC_NAME = "projects/sublime-sunspot-420109/topics/process_video"
SUBSCRIPTION_NAME = "projects/sublime-sunspot-420109/subscriptions/process_video-sub"

# Bucket names
BUCKET_TITLE = 'allcloudstorage1'
BUCKET_BACKGROUND = 'allcloudstorage2'
BUCKET_SUBTITLE = 'allcloudstorage3'
BUCKET_VIDEO = 'allcloudvideo'
BUCKET_OUTPUT = 'allcloudstorage4'

def publish_message(step, data):
    """Publishes a message to Pub/Sub with step information."""
    try:
        message = {
            'step': step,
            'data': data
        }
        publisher.publish(TOPIC_NAME, str(message).encode('utf-8'))
        logging.info(f"Published message for step '{step}' with data: {data}")
    except Exception as e:
        logging.exception(f"Error publishing message to Pub/Sub: {e}")

def download_files(data):
    """Step 1: Download the necessary files from GCS."""
    file_name = data.get('name')
    country = file_name.split('/')[0].capitalize()
    with tempfile.TemporaryDirectory() as tmpdir:
        subtitle_file = os.path.join(tmpdir, f'{country}.srt')
        video_file = os.path.join(tmpdir, 'original_video.mp4')

        # Download subtitle and video
        if not download_from_gcs(BUCKET_VIDEO, 'videos/original_video.mp4', video_file):
            return False
        if not download_from_gcs(BUCKET_SUBTITLE, file_name, subtitle_file):
            return False

        # Publish a message to indicate the next step
        publish_message('process_backgrounds', {'country': country, 'subtitle_file': subtitle_file, 'video_file': video_file})

def process_backgrounds(data):
    """Step 2: Process each background with the video and subtitle."""
    country = data['country']
    subtitle_file = data['subtitle_file']
    video_file = data['video_file']
    
    with tempfile.TemporaryDirectory() as tmpdir:
        title_file_path = os.path.join(tmpdir, f'{country}_title.txt')
        title_blob_name = find_title_file(BUCKET_TITLE, country)

        # Download the title file
        if title_blob_name:
            if not download_from_gcs(BUCKET_TITLE, title_blob_name, title_file_path):
                title_text = f"Video for {country}"
            else:
                with open(title_file_path, 'r', encoding='utf-8') as f:
                    title_text = f.read().strip()
        else:
            title_text = f"Video for {country}"

        backgrounds = ['background1.png', 'background2.png', 'background3.png']
        for bg in backgrounds:
            background_file = os.path.join(tmpdir, bg)
            output_file = os.path.join(tmpdir, f'{country}_{bg.split(".")[0]}_shorts.mp4')
            
            if not download_from_gcs(BUCKET_BACKGROUND, bg, background_file):
                continue
            
            if create_shorts_video(background_file, video_file, output_file, title_text, subtitle_file):
                # Publish a message to trigger the upload
                publish_message('upload_video', {'output_file': output_file, 'country': country, 'bg': bg})
    
def upload_video(data):
    """Step 3: Upload the processed video to GCS."""
    output_file = data['output_file']
    country = data['country']
    bg = data['bg']
    destination_blob_name = f'{country}/{bg.split(".")[0]}_shorts.mp4'
    
    if upload_to_gcs(BUCKET_OUTPUT, output_file, destination_blob_name):
        logging.info(f"Successfully uploaded {output_file} for {country} with background {bg}")
    else:
        logging.error(f"Failed to upload video for {country} with background {bg}")

def handle_pubsub_message(message):
    """Handles incoming Pub/Sub messages and triggers the appropriate function."""
    message_data = eval(message.data.decode('utf-8'))  # convert string back to dictionary
    step = message_data['step']
    data = message_data['data']
    
    if step == 'process_backgrounds':
        process_backgrounds(data)
    elif step == 'upload_video':
        upload_video(data)

    message.ack()

def start_processing(data):
    """Initial entry point for the workflow."""
    download_files(data)

if __name__ == "__main__":
    test_data = {
        'name': 'indonesia/original_video.mp4.srt'
    }
    start_processing(test_data)

    # Pub/Sub subscriber to listen for messages
    subscription_path = SUBSCRIPTION_NAME
    streaming_pull_future = subscriber.subscribe(subscription_path, callback=handle_pubsub_message)
    
    with subscriber:
        try:
            streaming_pull_future.result()
        except KeyboardInterrupt:
            streaming_pull_future.cancel()
