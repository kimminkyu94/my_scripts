import os
import tempfile
from google.cloud import storage
import ffmpeg
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)

# Google Cloud Storage client setup
storage_client = storage.Client()

# Bucket names
BUCKET_TITLE = 'allcloudstorage1'
BUCKET_BACKGROUND = 'allcloudstorage2'
BUCKET_SUBTITLE = 'allcloudstorage3'
BUCKET_VIDEO = 'allcloudvideo'
BUCKET_OUTPUT = 'allcloudstorage4'

def download_from_gcs(bucket_name, blob_name, destination_file_name):
    logging.info(f"Attempting to download {blob_name} from bucket {bucket_name}")
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
        logging.error(f"Error downloading {blob_name} from {bucket_name}: {e}")
        return False

def upload_to_gcs(bucket_name, source_file_name, destination_blob_name):
    logging.info(f"Attempting to upload {source_file_name} to bucket {bucket_name} as {destination_blob_name}")
    try:
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(destination_blob_name)
        blob.upload_from_filename(source_file_name)
        logging.info(f"Successfully uploaded {source_file_name} to {bucket_name}/{destination_blob_name}")
    except Exception as e:
        logging.error(f"Error uploading {source_file_name} to {bucket_name}/{destination_blob_name}: {e}")

def find_title_file(bucket_name, country):
    try:
        # Correct folder path for each country
        prefix = f'text/{country}/'
        bucket = storage_client.bucket(bucket_name)
        blobs = list(bucket.list_blobs(prefix=prefix))

        if not blobs:
            logging.error(f"No title file found in {country} directory with prefix {prefix}.")
            return None
        
        # Find the first .txt file in the directory
        for blob in blobs:
            if blob.name.endswith('.txt'):
                logging.info(f"Found title file: {blob.name}")
                return blob.name
        
        logging.error(f"No .txt title file found in {country} directory.")
        return None
        
    except Exception as e:
        logging.error(f"Error searching for title file in {country} directory: {e}")
        return None

def create_shorts_video(background, title, video, subtitle, output, title_text, subtitle_text):
    try:
        background_input = ffmpeg.input(background)
        video_input = (
            ffmpeg.input(video)
            .filter('scale', w=1080, h=775, force_original_aspect_ratio='decrease')
            .filter('pad', 1080, 775, '(ow-iw)/2', '(oh-ih)/2')
        )
        # Title overlay with proper transparency handling
        title_overlay = (
            ffmpeg.input('color=c=black:s=1080x1920', format='lavfi')
            .filter('drawtext', fontfile='/app/fonts/sans-serif-medium.ttf', fontsize=80, fontcolor='white', 
                    x='(w-tw)/2', y='h/6', text=title_text)
        )
        subtitle_overlay = (
            ffmpeg.input('color=c=black:s=1080x1920', format='lavfi')
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
    logging.info(f"Starting process_video function with data: {data}")
    file_name = data.get('name')
    if not file_name or not file_name.endswith('.srt'):
        logging.error(f"Invalid file name: {file_name}")
        return f"Invalid file name: {file_name}"

    country = file_name.split('/')[0]
    logging.info(f"Processing video for country: {country}")

    with tempfile.TemporaryDirectory() as tmpdir:
        title_file_path = os.path.join(tmpdir, f'{country}_title.txt')
        video_file = os.path.join(tmpdir, 'original_video.mp4')
        subtitle_file = os.path.join(tmpdir, f'{country}.srt')

        # Find the correct title file for the country
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
                    logging.error(f"Error reading title file {title_file_path}: {e}")
                    return f"Error reading title file for {country}"
        else:
            logging.warning(f"No title file found for {country}. Using default title.")
            title_text = f"Video for {country}"

        logging.info(f"Downloading video file: {video_blob_name}")
        if not download_from_gcs(BUCKET_VIDEO, video_blob_name, video_file):
            logging.error(f"Failed to download video file from {BUCKET_VIDEO}")
            return f"Failed to download video file from {BUCKET_VIDEO}"
        
        logging.info(f"Downloading subtitle file: {subtitle_blob_name}")
        if not download_from_gcs(BUCKET_SUBTITLE, subtitle_blob_name, subtitle_file):
            logging.error(f"Failed to download subtitle file for {country}")
            return f"Failed to download subtitle file for {country}"
        
        # Process the subtitle text
        try:
            logging.info(f"Reading subtitle file: {subtitle_file}")
            with open(subtitle_file, 'r', encoding='utf-8') as f:
                subtitle_lines = f.readlines()[2:]  # SRT format, skipping first two lines
                subtitle_text = ' '.join([line.strip() for line in subtitle_lines if line.strip()])
            logging.info(f"Subtitle text for {country}: {subtitle_text}")
        except Exception as e:
            logging.error(f"Error reading subtitle file {subtitle_file}: {e}")
            return f"Error reading subtitle file for {country}"
        
        # Process and create the video using the appropriate background and title
        backgrounds = ['background1.png', 'background2.png', 'background3.png']
        
        for bg in backgrounds:
            background_file = os.path.join(tmpdir, bg)
            output_file = os.path.join(tmpdir, f'{country}_{bg.split(".")[0]}_shorts.mp4')
            
            logging.info(f"Downloading background file: {bg}")
            if not download_from_gcs(BUCKET_BACKGROUND, bg, background_file):
                logging.error(f"Failed to download background {bg} for {country}")
                continue
            
            try:
                logging.info(f"Creating shorts video for {country} with background {bg}")
                create_shorts_video(background_file, title_file_path, video_file, subtitle_file, 
                                    output_file, title_text, subtitle_text)
            except Exception as e:
                logging.error(f"Error creating video for {country} with background {bg}: {str(e)}")
                continue
            
            try:
                logging.info(f"Uploading shorts video to GCS: {output_file}")
                upload_to_gcs(BUCKET_OUTPUT, output_file, f'{country}/{bg.split(".")[0]}_shorts.mp4')
            except Exception as e:
                logging.error(f"Error uploading video for {country} with background {bg}: {str(e)}")
        
    logging.info(f"Completed processing videos for {country}")
    return f"Processed videos for {country}"

def main(data):
    return process_video(data)

if __name__ == "__main__":
    test_data = {
        'name': 'america/original_video.mp4.srt'
    }
    result = main(test_data)
    print(result)
