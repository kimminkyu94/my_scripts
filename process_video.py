import os
import tempfile
import logging
from google.cloud import storage, pubsub_v1
import ffmpeg
from google.api_core import retry

# 로깅 설정 개선
logging.basicConfig(level=logging.DEBUG, 
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Google Cloud 클라이언트 설정
storage_client = storage.Client()
publisher = pubsub_v1.PublisherClient()
subscriber = pubsub_v1.SubscriberClient()

# Pub/Sub 토픽 및 구독 설정
PROJECT_ID = "sublime-sunspot-420109"
TOPIC_NAME = f"projects/{PROJECT_ID}/topics/process_video"
SUBSCRIPTION_NAME = f"projects/{PROJECT_ID}/subscriptions/process_video-sub"

# 버킷 이름 설정
BUCKET_TITLE = 'allcloudstorage1'
BUCKET_BACKGROUND = 'allcloudstorage2'
BUCKET_SUBTITLE = 'allcloudstorage3'
BUCKET_VIDEO = 'allcloudvideo'
BUCKET_OUTPUT = 'allcloudstorage4'

@retry.Retry(predicate=retry.if_exception_type(Exception))
def publish_message(step, data):
    """Pub/Sub에 메시지를 발행하는 함수"""
    try:
        message = {
            'step': step,
            'data': data
        }
        future = publisher.publish(TOPIC_NAME, str(message).encode('utf-8'))
        message_id = future.result()
        logger.info(f"Published message for step '{step}' with ID: {message_id}")
    except Exception as e:
        logger.exception(f"Error publishing message to Pub/Sub: {e}")
        raise

def download_from_gcs(bucket_name, source_blob_name, destination_file_name):
    """GCS에서 파일을 다운로드하는 함수"""
    try:
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(source_blob_name)
        blob.download_to_filename(destination_file_name)
        logger.info(f"Downloaded {source_blob_name} to {destination_file_name}")
        return True
    except Exception as e:
        logger.exception(f"Error downloading {source_blob_name}: {e}")
        return False

def upload_to_gcs(bucket_name, source_file_name, destination_blob_name):
    """GCS에 파일을 업로드하는 함수"""
    try:
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(destination_blob_name)
        blob.upload_from_filename(source_file_name)
        logger.info(f"Uploaded {source_file_name} to {destination_blob_name}")
        return True
    except Exception as e:
        logger.exception(f"Error uploading {source_file_name}: {e}")
        return False

def find_title_file(bucket_name, country):
    """제목 파일을 찾는 함수"""
    try:
        bucket = storage_client.bucket(bucket_name)
        blobs = bucket.list_blobs(prefix=f"{country}/")
        for blob in blobs:
            if blob.name.endswith('.txt'):
                return blob.name
        logger.warning(f"No title file found for {country}")
        return None
    except Exception as e:
        logger.exception(f"Error finding title file for {country}: {e}")
        return None

def create_shorts_video(background_file, video_file, output_file, title_text, subtitle_file):
    """비디오 생성 함수"""
    try:
        # ffmpeg 명령어 구성 및 실행
        # (이 부분은 실제 ffmpeg 명령어에 맞게 수정해야 합니다)
        (
            ffmpeg
            .input(background_file)
            .overlay(video_file)
            .drawtext(text=title_text)
            .filter('subtitles', subtitle_file)
            .output(output_file)
            .overwrite_output()
            .run(capture_stdout=True, capture_stderr=True)
        )
        logger.info(f"Created shorts video: {output_file}")
        return True
    except ffmpeg.Error as e:
        logger.error(f"Error creating shorts video: {e.stderr.decode()}")
        return False
    except Exception as e:
        logger.exception(f"Unexpected error creating shorts video: {e}")
        return False

def download_files(data):
    """파일 다운로드 함수"""
    try:
        file_name = data.get('name')
        country = file_name.split('/')[0].capitalize()
        with tempfile.TemporaryDirectory() as tmpdir:
            subtitle_file = os.path.join(tmpdir, f'{country}.srt')
            video_file = os.path.join(tmpdir, 'original_video.mp4')

            if not download_from_gcs(BUCKET_VIDEO, 'videos/original_video.mp4', video_file):
                raise Exception("Failed to download video file")
            if not download_from_gcs(BUCKET_SUBTITLE, file_name, subtitle_file):
                raise Exception("Failed to download subtitle file")

            publish_message('process_backgrounds', {
                'country': country,
                'subtitle_file': subtitle_file,
                'video_file': video_file
            })
    except Exception as e:
        logger.exception(f"Error in download_files: {e}")
        publish_message('error', {'step': 'download_files', 'error': str(e)})

def process_backgrounds(data):
    """배경 처리 함수"""
    try:
        country = data['country']
        subtitle_file = data['subtitle_file']
        video_file = data['video_file']
        
        with tempfile.TemporaryDirectory() as tmpdir:
            title_file_path = os.path.join(tmpdir, f'{country}_title.txt')
            title_blob_name = find_title_file(BUCKET_TITLE, country)

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
                    logger.warning(f"Failed to download background: {bg}")
                    continue
                
                if create_shorts_video(background_file, video_file, output_file, title_text, subtitle_file):
                    publish_message('upload_video', {
                        'output_file': output_file,
                        'country': country,
                        'bg': bg
                    })
                else:
                    logger.error(f"Failed to create shorts video for {country} with background {bg}")
    except Exception as e:
        logger.exception(f"Error in process_backgrounds: {e}")
        publish_message('error', {'step': 'process_backgrounds', 'error': str(e)})

def upload_video(data):
    """비디오 업로드 함수"""
    try:
        output_file = data['output_file']
        country = data['country']
        bg = data['bg']
        destination_blob_name = f'{country}/{bg.split(".")[0]}_shorts.mp4'
        
        if upload_to_gcs(BUCKET_OUTPUT, output_file, destination_blob_name):
            logger.info(f"Successfully uploaded {output_file} for {country} with background {bg}")
        else:
            logger.error(f"Failed to upload video for {country} with background {bg}")
    except Exception as e:
        logger.exception(f"Error in upload_video: {e}")
        publish_message('error', {'step': 'upload_video', 'error': str(e)})

def handle_pubsub_message(message):
    """Pub/Sub 메시지 처리 함수"""
    try:
        message_data = eval(message.data.decode('utf-8'))
        step = message_data['step']
        data = message_data['data']
        
        if step == 'process_backgrounds':
            process_backgrounds(data)
        elif step == 'upload_video':
            upload_video(data)
        elif step == 'error':
            logger.error(f"Received error message: {data}")
        else:
            logger.warning(f"Unknown step received: {step}")
        
        message.ack()
    except Exception as e:
        logger.exception(f"Error handling Pub/Sub message: {e}")
        message.nack()

def main(data):
    """메인 함수"""
    try:
        logger.info("Starting video processing")
        download_files(data)
    except Exception as e:
        logger.exception(f"Error in main function: {e}")
        publish_message('error', {'step': 'main', 'error': str(e)})

if __name__ == "__main__":
    logging.info("Starting the application")
    test_data = {
        'name': 'indonesia/original_video.mp4.srt'
    }
    main(test_data)

    # Pub/Sub 구독 설정
    with subscriber:
        subscription_path = subscriber.subscription_path(PROJECT_ID, SUBSCRIPTION_NAME)
        streaming_pull_future = subscriber.subscribe(subscription_path, callback=handle_pubsub_message)
        logger.info(f"Listening for messages on {subscription_path}")
        
        try:
            streaming_pull_future.result()
        except KeyboardInterrupt:
            streaming_pull_future.cancel()
            logger.info("Streaming pull future cancelled.")
        except Exception as e:
            logger.exception(f"Unexpected error in Pub/Sub listener: {e}")

logger.info("Application terminated")
