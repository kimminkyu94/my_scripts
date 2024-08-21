import os
import logging
from google.cloud import storage, pubsub_v1
import ffmpeg
from google.api_core import retry

# 로깅 설정
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s')
logger = logging.getLogger(__name__)

# Google Cloud 클라이언트 설정
storage_client = storage.Client()
publisher = pubsub_v1.PublisherClient()

# Pub/Sub 및 Storage 설정
PROJECT_ID = os.environ.get('PROJECT_ID', 'your-project-id')
TOPIC_NAME = f"projects/{PROJECT_ID}/topics/process_video"
BUCKET_TITLE = os.environ.get('BUCKET_TITLE', 'allcloudstorage1')
BUCKET_BACKGROUND = os.environ.get('BUCKET_BACKGROUND', 'allcloudstorage2')
BUCKET_SUBTITLE = os.environ.get('BUCKET_SUBTITLE', 'allcloudstorage3')
BUCKET_VIDEO = os.environ.get('BUCKET_VIDEO', 'allcloudvideo')
BUCKET_OUTPUT = os.environ.get('BUCKET_OUTPUT', 'allcloudstorage4')

@retry.Retry(predicate=retry.if_exception_type(Exception))
def publish_message(step, data):
    """Pub/Sub에 메시지를 발행하는 함수"""
    try:
        message = {'step': step, 'data': data}
        future = publisher.publish(TOPIC_NAME, str(message).encode('utf-8'))
        message_id = future.result()
        logger.info(f"Published message for step '{step}' with ID: {message_id}")
        return message_id
    except Exception as e:
        logger.exception(f"Error publishing message to Pub/Sub: {e}")
        raise

def get_gcs_uri(bucket_name, blob_name):
    """GCS URI를 생성하는 함수"""
    return f"gs://{bucket_name}/{blob_name}"

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

def create_shorts_video(background_uri, video_uri, output_uri, title_text, subtitle_uri):
    """비디오 생성 함수"""
    try:
        # ffmpeg 명령어 구성 및 실행
        (
            ffmpeg
            .input(background_uri)
            .overlay(ffmpeg.input(video_uri))
            .drawtext(text=title_text)
            .filter('subtitles', subtitle_uri)
            .output(output_uri, vcodec='libx264', acodec='aac')
            .overwrite_output()
            .run(capture_stdout=True, capture_stderr=True)
        )
        logger.info(f"Created shorts video: {output_uri}")
        return True
    except ffmpeg.Error as e:
        logger.error(f"Error creating shorts video: {e.stderr.decode()}")
        return False
    except Exception as e:
        logger.exception(f"Unexpected error creating shorts video: {e}")
        return False

def process_video(data):
    """비디오 처리 메인 함수"""
    try:
        file_name = data.get('name')
        if not file_name:
            raise ValueError("No 'name' provided in the data")
        country = file_name.split('/')[0].capitalize()
        
        # URI 생성
        video_uri = get_gcs_uri(BUCKET_VIDEO, 'videos/original_video.mp4')
        subtitle_uri = get_gcs_uri(BUCKET_SUBTITLE, file_name)

        # 제목 파일 처리
        title_blob_name = find_title_file(BUCKET_TITLE, country)
        if title_blob_name:
            title_uri = get_gcs_uri(BUCKET_TITLE, title_blob_name)
            with storage_client.bucket(BUCKET_TITLE).blob(title_blob_name).open("r") as f:
                title_text = f.read().strip()
        else:
            title_text = f"Video for {country}"

        # 배경 처리
        backgrounds = ['background1.png', 'background2.png', 'background3.png']
        for bg in backgrounds:
            background_uri = get_gcs_uri(BUCKET_BACKGROUND, bg)
            output_uri = get_gcs_uri(BUCKET_OUTPUT, f'{country}/{bg.split(".")[0]}_shorts.mp4')
            
            if create_shorts_video(background_uri, video_uri, output_uri, title_text, subtitle_uri):
                logger.info(f"Successfully processed video for {country} with background {bg}")
                publish_message('video_created', {'country': country, 'background': bg, 'output_uri': output_uri})
            else:
                logger.error(f"Failed to create shorts video for {country} with background {bg}")
                publish_message('video_creation_failed', {'country': country, 'background': bg})

        return {"status": "success", "message": f"Processed video for {country}"}
    except Exception as e:
        logger.exception(f"Error in process_video: {e}")
        publish_message('process_video_error', {'error': str(e)})
        return {"status": "error", "message": str(e)}

def main(data):
    """Cloud Run 진입점"""
    try:
        logger.info("Starting video processing")
        result = process_video(data)
        logger.info(f"Video processing completed with result: {result}")
        return result
    except Exception as e:
        logger.exception(f"Error in main function: {e}")
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    # 로컬 테스트용 코드
    test_data = {
        'name': 'indonesia/original_video.mp4.srt'
    }
    result = main(test_data)
    print(f"Test result: {result}")
