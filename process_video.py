import os
import tempfile
import json
from google.cloud import storage, tasks_v2
import ffmpeg
import logging

# 로깅 설정
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

# Google Cloud 클라이언트 설정
storage_client = storage.Client()
tasks_client = tasks_v2.CloudTasksClient()

# 버킷 이름
BUCKET_TITLE = 'allcloudstorage1'
BUCKET_BACKGROUND = 'allcloudstorage2'
BUCKET_SUBTITLE = 'allcloudstorage3'
BUCKET_VIDEO = 'allcloudvideo'
BUCKET_OUTPUT = 'allcloudstorage4'

# Cloud Tasks 큐 설정
PROJECT_ID = 'sublime-sunspot-420109'
QUEUE_LOCATION = 'us-central1'
QUEUE_NAME = 'video-processing-queue'
QUEUE_PATH = tasks_client.queue_path(PROJECT_ID, QUEUE_LOCATION, QUEUE_NAME)

def download_from_gcs(bucket_name, blob_name, destination_file_name):
    logging.debug(f"Downloading {blob_name} from {bucket_name}")
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    blob.download_to_filename(destination_file_name)
    logging.info(f"Downloaded {blob_name}")
    return True

def upload_to_gcs(bucket_name, source_file_name, destination_blob_name):
    logging.debug(f"Uploading {source_file_name} to {bucket_name}/{destination_blob_name}")
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(destination_blob_name)
    blob.upload_from_filename(source_file_name)
    logging.info(f"Uploaded {source_file_name}")
    return True

def find_title_file(bucket_name, country):
    logging.debug(f"Finding title file for {country}")
    bucket = storage_client.bucket(bucket_name)
    blobs = bucket.list_blobs(prefix=f'text/{country}/')
    for blob in blobs:
        if blob.name.lower().endswith(('.txt', '.text')):
            logging.info(f"Found title file: {blob.name}")
            return blob.name
    logging.warning(f"No title file found for {country}")
    return None

def create_shorts_video(background, video, output, title_text, subtitle_text):
    try:
        ffmpeg_cmd = (
            ffmpeg
            .input(background)
            .overlay(ffmpeg.input(video).filter('scale', 1080, -1))
            .drawtext(fontfile='/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', fontsize=80, text=title_text, x='(w-tw)/2', y='h*0.1')
            .drawtext(fontfile='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', fontsize=60, text=subtitle_text, x='(w-tw)/2', y='h*0.9')
            .output(output, vcodec='libx264', preset='ultrafast', crf=23)
        )
        ffmpeg_cmd.run(capture_stdout=True, capture_stderr=True)
        logging.info(f"Created shorts video: {output}")
        return True
    except ffmpeg.Error as e:
        logging.error(f"FFmpeg error: {e.stderr.decode('utf8')}")
        return False

def process_video(data):
    logging.info(f"Processing video: {data}")
    country = data['name'].split('/')[0].capitalize()
    
    with tempfile.TemporaryDirectory() as tmpdir:
        title_file = os.path.join(tmpdir, f'{country}_title.txt')
        video_file = os.path.join(tmpdir, 'original_video.mp4')
        subtitle_file = os.path.join(tmpdir, f'{country}.srt')
        
        # 파일 다운로드
        title_blob = find_title_file(BUCKET_TITLE, country)
        if title_blob:
            download_from_gcs(BUCKET_TITLE, title_blob, title_file)
            with open(title_file, 'r', encoding='utf-8') as f:
                title_text = f.read().strip()
        else:
            title_text = f"Video for {country}"
        
        download_from_gcs(BUCKET_VIDEO, 'videos/original_video.mp4', video_file)
        download_from_gcs(BUCKET_SUBTITLE, data['name'], subtitle_file)
        
        with open(subtitle_file, 'r', encoding='utf-8') as f:
            subtitle_lines = f.readlines()[2:]
            subtitle_text = ' '.join([line.strip() for line in subtitle_lines if line.strip()])
        
        # 비디오 처리
        backgrounds = ['background1.png', 'background2.png', 'background3.png']
        for bg in backgrounds:
            bg_file = os.path.join(tmpdir, bg)
            output_file = os.path.join(tmpdir, f'{country}_{bg.split(".")[0]}_shorts.mp4')
            
            download_from_gcs(BUCKET_BACKGROUND, bg, bg_file)
            if create_shorts_video(bg_file, video_file, output_file, title_text, subtitle_text):
                upload_to_gcs(BUCKET_OUTPUT, output_file, f'{country}/{bg.split(".")[0]}_shorts.mp4')
    
    logging.info(f"Completed processing video for {country}")
    return f"Processed video for {country}"

def enqueue_video_processing(data):
    task = {
        'http_request': {
            'http_method': tasks_v2.HttpMethod.POST,
            'url': 'https://subtitle-service-22hpg2idaq-uc.a.run.app/process_video',
            'body': json.dumps(data).encode()
        }
    }
    response = tasks_client.create_task(parent=QUEUE_PATH, task=task)
    logging.info(f"Created task: {response.name}")
    return response

def main(request):
    if request.method == 'POST':
        data = request.get_json()
        if 'process' in data:
            return process_video(data)
        else:
            enqueue_video_processing(data)
            return 'Task enqueued', 202
    else:
        return 'Send a POST request to process video', 400

if __name__ == "__main__":
    test_data = {
        'name': 'america/original_video.mp4.srt'
    }
    result = main(type('Request', (), {'method': 'POST', 'get_json': lambda: test_data})())
    print(result)
