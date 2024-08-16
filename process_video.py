import os
import tempfile
from google.cloud import storage
import ffmpeg
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO)

# Google Cloud Storage 클라이언트 설정
storage_client = storage.Client()

# 버킷 이름 설정
BUCKET_TITLE = 'allcloudstorage1'
BUCKET_BACKGROUND = 'allcloudstorage2'
BUCKET_SUBTITLE = 'allcloudstorage3'
BUCKET_VIDEO = 'allcloudvideo'
BUCKET_OUTPUT = 'allcloudstorage4'

def download_from_gcs(bucket_name, blob_name, destination_file_name):
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    blob.download_to_filename(destination_file_name)
    logging.info(f"Downloaded {blob_name} from {bucket_name}")

def upload_to_gcs(bucket_name, source_file_name, destination_blob_name):
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(destination_blob_name)
    blob.upload_from_filename(source_file_name)
    logging.info(f"Uploaded {source_file_name} to {bucket_name}/{destination_blob_name}")

def create_shorts_video(background, title, video, subtitle, output, title_text, subtitle_text):
    try:
        background_input = ffmpeg.input(background)
        video_input = (
            ffmpeg.input(video)
            .filter('scale', w=1080, h=775, force_original_aspect_ratio='decrease')
            .filter('pad', 1080, 775, '(ow-iw)/2', '(oh-ih)/2')
        )
        title_overlay = (
            ffmpeg.input('color=transparent:s=1080x1920', format='lavfi')
            .filter('drawtext', fontfile='/app/fonts/sans-serif-medium.ttf', fontsize=80, fontcolor='white', 
                    x='(w-tw)/2', y='h/6', text=title_text)
        )
        subtitle_overlay = (
            ffmpeg.input('color=transparent:s=1080x1920', format='lavfi')
            .filter('drawtext', fontfile='/app/fonts/sans-serif-light.ttf', fontsize=60, fontcolor='white', 
                    x='(w-tw)/2', y='h-th-20', text=subtitle_text)
            .filter('geq', r='r(X,Y)', g='g(X,Y)', b='b(X,Y)', 
                    a='if(lt(Y,(H-h)+60),255,0)')
        )
        output = (
            background_input
            .overlay(video_input, x='(W-w)/2', y='(H-h)/2')
            .overlay(title_overlay)
            .overlay(subtitle_overlay)
            .output(output, vcodec='libx264', acodec='aac', preset='medium', crf='23')
            .overwrite_output()
        )
        output.run(capture_stdout=True, capture_stderr=True)
        logging.info(f"Created shorts video: {output}")
    except ffmpeg.Error as e:
        logging.error(f"FFmpeg error: {e.stderr.decode('utf8')}")
        raise

def process_video(data):
    file_name = data.get('name')
    if not file_name or not file_name.endswith('.srt'):
        logging.error(f"Invalid file name: {file_name}")
        return f"Invalid file name: {file_name}"

    country = file_name.split('.')[0]
    logging.info(f"Processing video for country: {country}")

    with tempfile.TemporaryDirectory() as tmpdir:
        backgrounds = ['background1.png', 'background2.png', 'background3.png']
        
        title_file = os.path.join(tmpdir, f'{country}_title.png')
        video_file = os.path.join(tmpdir, f'{country}.mp4')
        subtitle_file = os.path.join(tmpdir, f'{country}.srt')
        
        # 필요한 파일 다운로드
        download_from_gcs(BUCKET_TITLE, f'text/{country}/{country}_title.png', title_file)
        download_from_gcs(BUCKET_VIDEO, 'videos/original_video.mp4', video_file)
        download_from_gcs(BUCKET_SUBTITLE, f'{country}/{file_name}', subtitle_file)
        
        # 제목과 자막 텍스트 읽기
        with open(title_file, 'r', encoding='utf-8') as f:
            title_text = f.read().strip()
        
        with open(subtitle_file, 'r', encoding='utf-8') as f:
            subtitle_lines = f.readlines()[2:]  # SRT 형식에서 첫 두 줄 건너뛰기
            subtitle_text = ' '.join([line.strip() for line in subtitle_lines if line.strip()])
        
        for bg in backgrounds:
            background_file = os.path.join(tmpdir, bg)
            output_file = os.path.join(tmpdir, f'{country}_{bg.split(".")[0]}_shorts.mp4')
            
            download_from_gcs(BUCKET_BACKGROUND, bg, background_file)
            
            # 숏츠 비디오 생성
            create_shorts_video(background_file, title_file, video_file, subtitle_file, 
                                output_file, title_text, subtitle_text)
            
            # 결과물 업로드 (나라별로 저장)
            upload_to_gcs(BUCKET_OUTPUT, output_file, f'{country}/{bg.split(".")[0]}_shorts.mp4')
        
    logging.info(f"Completed processing videos for {country}")
    return f"Processed videos for {country}"

if __name__ == "__main__":
    # 로컬 테스트용 코드
    test_data = {
        'name': 'test.srt'
    }
    result = process_video(test_data)
    print(result)
