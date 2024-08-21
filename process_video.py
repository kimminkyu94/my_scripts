import os
import logging
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

def find_title_file(bucket_name, country):
    """제목 파일을 찾는 함수"""
    try:
        bucket = storage_client.bucket(bucket_name)
        blobs = bucket.list_blobs(prefix=f"text/{country}/")
        for blob in blobs:
            if blob.name.lower().endswith('.txt'):
                return blob.name
        logger.warning(f"No title file found for {country}")
        return None
    except Exception as e:
        logger.exception(f"Error finding title file for {country}: {e}")
        return None

def create_shorts_video(background_file, video_file, output_file, title_text, subtitle_file):
    """비디오 생성 함수"""
    try:
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
        
        tmp_dir = '/tmp'
        background_file = os.path.join(tmp_dir, 'background.png')
        video_file = os.path.join(tmp_dir, 'video.mp4')
        subtitle_file = os.path.join(tmp_dir, 'subtitle.srt')
        
        # 파일 다운로드
        storage_client.bucket(BUCKET_BACKGROUND).blob('background1.png').download_to_filename(background_file)
        storage_client.bucket(BUCKET_VIDEO).blob('videos/original_video.mp4').download_to_filename(video_file)
        storage_client.bucket(BUCKET_SUBTITLE).blob(file_name).download_to_filename(subtitle_file)

        # 제목 파일 처리
        title_blob_name = find_title_file(BUCKET_TITLE, country)
        if title_blob_name:
            title_file = os.path.join(tmp_dir, 'title.txt')
            storage_client.bucket(BUCKET_TITLE).blob(title_blob_name).download_to_filename(title_file)
            with open(title_file, 'r', encoding='utf-8') as f:
                title_text = f.read().strip()
            os.remove(title_file)  # 임시 제목 파일 삭제
        else:
            title_text = f"Video for {country}"

        output_file = os.path.join(tmp_dir, f'{country}_shorts.mp4')
        
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

        return {"status": "success", "message": f"Processed video for {country}"}
    except Exception as e:
        logger.exception(f"Error in process_video: {e}")
        return {"status": "error", "message": str(e)}

def main(request):
    """Cloud Run 진입점"""
    try:
        logger.info("Starting video processing")
        data = request.get_json()
        if not data:
            raise ValueError("No data provided in the request")
        
        result = process_video(data)
        logger.info(f"Video processing completed with result: {result}")
        return result
    except Exception as e:
        logger.exception(f"Error in main function: {e}")
        return {"status": "error", "message": str(e)}, 500
