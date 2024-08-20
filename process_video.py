import os
import tempfile
from google.cloud import storage
import ffmpeg
import logging

# Set up logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

# Google Cloud Storage client setup
storage_client = storage.Client()

# Bucket names
BUCKET_TITLE = 'allcloudstorage1'
BUCKET_BACKGROUND = 'allcloudstorage2'
BUCKET_SUBTITLE = 'allcloudstorage3'
BUCKET_VIDEO = 'allcloudvideo'
BUCKET_OUTPUT = 'allcloudstorage4'

def download_from_gcs(bucket_name, blob_name, destination_file_name):
    logging.debug(f"Attempting to download {blob_name} from bucket {bucket_name}")
    try:
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        if not blob.exists():
            logging.error(f"File {blob_name} does not exist in bucket {bucket_name}")
            return False
        blob.download_to_filename(destination_file_name)
        logging.info(f"Successfully downloaded {blob_name} from {bucket_name}")
        return True
    except Exception as e:
        logging.exception(f"Error downloading {blob_name} from {bucket_name}: {e}")
        return False

def upload_to_gcs(bucket_name, source_file_name, destination_blob_name):
    logging.debug(f"Attempting to upload {source_file_name} to bucket {bucket_name} as {destination_blob_name}")
    try:
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(destination_blob_name)
        blob.upload_from_filename(source_file_name)
        logging.info(f"Successfully uploaded {source_file_name} to {bucket_name}/{destination_blob_name}")
        return True
    except Exception as e:
        logging.exception(f"Error uploading {source_file_name} to {bucket_name}/{destination_blob_name}: {e}")
        return False

def find_title_file(bucket_name, country):
    logging.debug(f"Searching for title file for country: {country}")
    try:
        prefix = f'text/{country.lower()}/'
        bucket = storage_client.bucket(bucket_name)
        blobs = list(bucket.list_blobs(prefix=prefix))

        logging.debug(f"Found {len(blobs)} files in {prefix}")
        
        for blob in blobs:
            logging.debug(f"Checking file: {blob.name}")
            if blob.name.lower().endswith(('.txt', '.text')):
                logging.info(f"Found title file: {blob.name}")
                return blob.name
        
        logging.warning(f"No title file found for {country} in {prefix}")
        return None
        
    except Exception as e:
        logging.exception(f"Error searching for title file in {country} directory: {e}")
        return None

def create_shorts_video(background, video, output, title_text, subtitle_text):
    logging.debug(f"Creating shorts video with background: {background}")
    try:
        background_input = ffmpeg.input(background)
        video_input = (
            ffmpeg.input(video)
            .filter('scale', w=1080, h=775, force_original_aspect_ratio='decrease')
            .filter('pad', 1080, 775, '(ow-iw)/2', '(oh-ih)/2')
        )
        title_overlay = (
            ffmpeg.input('color=c=black@0:s=1080x1920', format='lavfi')
            .filter('drawtext', fontfile='/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', fontsize=80, fontcolor='white', 
                    x='(w-tw)/2', y='h/6', text=title_text)
            .filter('crop', 'iw', 'min(ih,100)')
        )
        subtitle_overlay = (
            ffmpeg.input('color=c=black@0:s=1080x1920', format='lavfi')
            .filter('drawtext', fontfile='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', fontsize=60, fontcolor='white', 
                    x='(w-tw)/2', y='h-th-20', text=subtitle_text)
            .filter('crop', 'iw', 'min(ih,60)')
        )
        output = (
            background_input
            .overlay(video_input, x='(W-w)/2', y='(H-h)/2')
            .overlay(title_overlay, y=0)
            .overlay(subtitle_overlay, y='H-h')
            .output(output, vcodec='libx264', acodec='aac', preset='medium', crf='23')
            .overwrite_output()
        )
        logging.debug(f"FFmpeg command: {' '.join(ffmpeg.compile(output))}")
        output.run(capture_stdout=True, capture_stderr=True)
        logging.info(f"Successfully created shorts video: {output}")
        return True
    except ffmpeg.Error as e:
        logging.error(f"FFmpeg error: {e.stderr.decode('utf8')}")
        logging.error(f"FFmpeg command: {' '.join(e.cmd)}")
        return False
    except Exception as e:
        logging.exception(f"Unexpected error in create_shorts_video: {e}")
        return False

def process_video(data):
    logging.info(f"Starting process_video function with data: {data}")
    file_name = data.get('name')
    if not file_name or not file_name.endswith('.srt'):
        logging.error(f"Invalid file name: {file_name}")
        return f"Invalid file name: {file_name}"

    country = file_name.split('/')[0].replace('_', ' ')
    logging.info(f"Processing video for country: {country}")

    with tempfile.TemporaryDirectory() as tmpdir:
        title_file_path = os.path.join(tmpdir, f'{country}_title.txt')
        video_file = os.path.join(tmpdir, 'original_video.mp4')
        subtitle_file = os.path.join(tmpdir, f'{country}.srt')

        title_blob_name = find_title_file(BUCKET_TITLE, country)
        subtitle_blob_name = file_name
        video_blob_name = 'videos/original_video.mp4'

        if title_blob_name:
            logging.info(f"Downloading title file: {title_blob_name}")
            if not download_from_gcs(BUCKET_TITLE, title_blob_name, title_file_path):
                logging.warning(f"Failed to download title file for {country}. Using default title.")
                title_text = f"Video for {country}"
            else:
                try:
                    with open(title_file_path, 'r', encoding='utf-8') as f:
                        title_text = f.read().strip()
                    logging.info(f"Title text for {country}: {title_text}")
                except Exception as e:
                    logging.exception(f"Error reading title file {title_file_path}: {e}")
                    return f"Error reading title file for {country}"
        else:
            logging.warning(f"No title file found for {country}. Using default title.")
            title_text = f"Video for {country}"

        if not download_from_gcs(BUCKET_VIDEO, video_blob_name, video_file):
            logging.error(f"Failed to download video file from {BUCKET_VIDEO}")
            return f"Failed to download video file from {BUCKET_VIDEO}"
        
        if not download_from_gcs(BUCKET_SUBTITLE, subtitle_blob_name, subtitle_file):
            logging.error(f"Failed to download subtitle file for {country}")
            return f"Failed to download subtitle file for {country}"
        
        try:
            with open(subtitle_file, 'r', encoding='utf-8') as f:
                subtitle_lines = f.readlines()[2:]  # SRT format, skipping first two lines
                subtitle_text = ' '.join([line.strip() for line in subtitle_lines if line.strip()])
            logging.info(f"Subtitle text for {country}: {subtitle_text}")
        except Exception as e:
            logging.exception(f"Error reading subtitle file {subtitle_file}: {e}")
            return f"Error reading subtitle file for {country}"
        
        backgrounds = ['background1.png', 'background2.png', 'background3.png']
        
        for bg in backgrounds:
            background_file = os.path.join(tmpdir, bg)
            output_file = os.path.join(tmpdir, f'{country}_{bg.split(".")[0]}_shorts.mp4')
            
            if not download_from_gcs(BUCKET_BACKGROUND, bg, background_file):
                logging.error(f"Failed to download background {bg} for {country}")
                continue
            
            if create_shorts_video(background_file, video_file, output_file, title_text, subtitle_text):
                if upload_to_gcs(BUCKET_OUTPUT, output_file, f'{country}/{bg.split(".")[0]}_shorts.mp4'):
                    logging.info(f"Successfully processed and uploaded video for {country} with background {bg}")
                else:
                    logging.error(f"Failed to upload video for {country} with background {bg}")
            else:
                logging.error(f"Failed to create video for {country} with background {bg}")
        
    logging.info(f"Completed processing videos for {country}")
    return f"Processed videos for {country}"

def main(data):
    try:
        return process_video(data)
    except Exception as e:
        logging.exception(f"Unexpected error in main function: {e}")
        return f"Error processing video: {str(e)}"

if __name__ == "__main__":
    test_data = {
        'name': 'indonesia/original_video.mp4.srt'
    }
    result = main(test_data)
    print(result)
