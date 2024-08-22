import os
import logging
import uuid
import shutil
from google.cloud import storage
import ffmpeg

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s')
logger = logging.getLogger(__name__)

# Google Cloud Storage 클라이언트 설정
storage_client = storage.Client()

# 버킷 이름 설정
BUCKET_TITLE = 'allcloudstorage1'
BUCKET_BACKGROUND = 'allcloudstorage2'
BUCKET_SUBTITLE = 'allcloudstorage3'
BUCKET_VIDEO = 'allcloudvideo'
BUCKET_OUTPUT = 'allcloudstorage4'

def check_tmp_directory():
    if not os.path.exists('/tmp'):
        logger.error("/tmp directory does not exist")
        return False
    if not os.access('/tmp', os.W_OK):
        logger.error("No write permission to /tmp")
        return False
    total, used, free = shutil.disk_usage("/tmp")
    logger.info(f"Free space in /tmp: {free // (2**20)} MB")
    return True

def find_title_file(bucket_name, country):
    """제목 파일을 찾는 함수"""
    try:
        logger.info(f"Searching for title file in bucket {bucket_name} for country {country}")
        bucket = storage_client.bucket(bucket_name)
        blobs = bucket.list_blobs(prefix=f"text/{country}/")
        for blob in blobs:
            if blob.name.lower().endswith('.txt'):
                logger.info(f"Found title file: {blob.name}")
                return blob.name
        logger.warning(f"No title file found for {country}")
        return None
    except Exception as e:
        logger.exception(f"Error finding title file for {country}: {e}")
        return None

def create_shorts_video(background_file, video_file, output_file, title_text, subtitle_file):
    """비디오 생성 함수"""
    try:
        logger.info(f"Creating shorts video with background: {background_file}, video: {video_file}, output: {output_file}")
        logger.info(f"Title text: {title_text}, Subtitle file: {subtitle_file}")
        (
            ffmpeg
            .input(background_file)
            .overlay(ffmpeg.input(video_file))
            .drawtext(text=title_text, fontsize=24, fontcolor='white', x='(w-text_w)/2', y='h-th-10')
            .filter('subtitles', subtitle_file)
            .output(output_file, vcodec='libx264', acodec='aac')
            .overwrite_output()
            .run(capture_stdout=True, capture_stderr=True)
        )
        logger.info(f"Created shorts video: {output_file}")
        return True
    except ffmpeg.Error as e:
        logger.error(f"FFmpeg error creating shorts video: {e.stderr.decode()}")
        return False
    except Exception as e:
        logger.exception(f"Unexpected error creating shorts video: {e}")
        return False

def process_video(data):
    """비디오 처리 메인 함수"""
    try:
        if not check_tmp_directory():
            raise EnvironmentError("Temporary directory is not accessible or has insufficient space")

        logger.info(f"Starting video processing with data: {data}")
        file_name = data.get('name')
        if not file_name:
            raise ValueError("No 'name' provided in the data")
        country = file_name.split('/')[0].capitalize()
        logger.info(f"Processing video for country: {country}")
        
        tmp_dir = '/tmp'
        unique_id = str(uuid.uuid4())
        background_file = os.path.join(tmp_dir, f'background_{unique_id}.png')
        video_file = os.path.join(tmp_dir, f'video_{unique_id}.mp4')
        subtitle_file = os.path.join(tmp_dir, f'subtitle_{unique_id}.srt')
        
        # 파일 다운로드
        logger.info("Downloading necessary files")
        try:
            storage_client.bucket(BUCKET_BACKGROUND).blob('background1.png').download_to_filename(background_file)
            storage_client.bucket(BUCKET_VIDEO).blob('videos/original_video.mp4').download_to_filename(video_file)
            storage_client.bucket(BUCKET_SUBTITLE).blob(file_name).download_to_filename(subtitle_file)
            logger.info("All files downloaded successfully")
        except Exception as e:
            logger.error(f"Error downloading files: {e}")
            raise

        # 제목 파일 처리
        title_blob_name = find_title_file(BUCKET_TITLE, country)
        if title_blob_name:
            title_file = os.path.join(tmp_dir, f'title_{unique_id}.txt')
            try:
                storage_client.bucket(BUCKET_TITLE).blob(title_blob_name).download_to_filename(title_file)
                logger.info(f"Successfully downloaded title file to {title_file}")
                with open(title_file, 'r', encoding='utf-8') as f:
                    title_text = f.read().strip()
                os.remove(title_file)
                logger.info(f"Title text: {title_text}")
            except Exception as e:
                logger.error(f"Error processing title file: {e}")
                title_text = f"Video for {country}"
        else:
            title_text = f"Video for {country}"
            logger.info(f"Using default title text: {title_text}")

        output_file = os.path.join(tmp_dir, f'{country}_shorts_{unique_id}.mp4')
        
        if create_shorts_video(background_file, video_file, output_file, title_text, subtitle_file):
            destination_blob_name = f'{country}/background1_shorts.mp4'
            storage_client.bucket(BUCKET_OUTPUT).blob(destination_blob_name).upload_from_filename(output_file)
            logger.info(f"Successfully processed and uploaded video for {country}")
        else:
            logger.error(f"Failed to create shorts video for {country}")

        # 임시 파일 삭제
        for file in [background_file, video_file, subtitle_file, output_file]:
            if os.path.exists(file):
                os.remove(file)
                logger.info(f"Removed temporary file: {file}")

        return {"status": "success", "message": f"Processed video for {country}"}
    except Exception as e:
        logger.exception(f"Error in process_video: {e}")
        return {"status": "error", "message": str(e)}

def main(request):
    """Cloud Run 진입점"""
    try:
        logger.info("Starting video processing")
        logger.info(f"Request type: {type(request)}")
        logger.info(f"Request content: {request}")
        
        data = request if isinstance(request, dict) else request.get_json()
        if not data:
            raise ValueError("No data provided in the request")
        
        result = process_video(data)
        logger.info(f"Video processing completed with result: {result}")
        return result
    except Exception as e:
        logger.exception(f"Error in main function: {e}")
        return {"status": "error", "message": str(e)}, 500

if __name__ == "__main__":
    # 로컬 테스트를 위한 코드
    test_request = {"name": "usa/subtitle.srt"}
    print(main(test_request))
