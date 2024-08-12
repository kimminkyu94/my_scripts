import logging
import requests
import json
import os
from google.cloud import storage
import traceback

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 환경 변수 로깅
logger.info("환경 변수 목록:")
for key, value in os.environ.items():
    if 'key' in key.lower() or 'api' in key.lower():
        logger.info(f"{key}: {value[:5]}...")  # API 키 관련 변수는 일부만 로깅
    else:
        logger.info(f"{key}: 설정됨")

# API 키 및 URL 설정
API_KEY = os.environ.get('API_KEY') or os.environ.get('OPENAI_API_KEY')
if not API_KEY:
    raise ValueError("API 키가 설정되지 않았습니다. 환경 변수를 확인해주세요.")
logger.info(f"API 키 확인: {API_KEY[:5]}...")  # 키의 앞부분만 출력

GPT_API_URL = 'https://api.openai.com/v1/chat/completions'
logger.info(f"GPT API URL: {GPT_API_URL}")

def translate_content(content):
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }
    data = {
        "model": "gpt-4",  # 사용할 모델 이름 또는 ID
        "messages": [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": content}
        ]
    }
    try:
        logger.info(f"Sending content to OpenAI GPT API: {GPT_API_URL}")
        response = requests.post(GPT_API_URL, headers=headers, json=data, timeout=30)
        response.raise_for_status()
        logger.info("OpenAI GPT API request successful")
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Error calling OpenAI GPT API: {e}")
        raise

def main(data):
    try:
        bucket_name = data['bucket']
        file_name = data['name']

        logger.info(f"Processing file: {file_name} from bucket: {bucket_name}")

        storage_client = storage.Client()
        bucket = storage_client.get_bucket(bucket_name)
        blob = bucket.blob(file_name)

        try:
            logger.info(f"Downloading file: {file_name} from bucket: {bucket_name}")
            content = blob.download_as_string().decode('utf-8')
            logger.info(f"File content (first 100 chars): {content[:100]}...")
        except Exception as e:
            logger.error(f"Error downloading file: {e}")
            raise

        try:
            translated_contents = translate_content(content)
            if not translated_contents:
                raise ValueError('Translated content is empty or missing')
            logger.info(f"Translation successful. Results: {list(translated_contents.keys())}")
        except json.JSONDecodeError as e:
            logger.error(f"Error decoding OpenAI GPT API response: {e}")
            raise
        except ValueError as e:
            logger.error(f"Error processing OpenAI GPT API response: {e}")
            raise

        output_bucket_name = "allcloudstorage3"
        output_bucket = storage_client.get_bucket(output_bucket_name)

        for key, content in translated_contents.items():
            try:
                logger.info(f"Saving translated file for {key} to bucket: {output_bucket_name}")
                
                # 데이터 타입에 따른 처리
                if isinstance(content, dict):
                    content = json.dumps(content)
                elif isinstance(content, list):
                    content = json.dumps(content)
                elif isinstance(content, (int, float)):
                    content = str(content)
                elif not isinstance(content, str):
                    content = str(content)
                
                output_blob = output_bucket.blob(f"{key}/{file_name}")
                output_blob.upload_from_string(content)
                logger.info(f"Successfully saved file for {key}")
            except Exception as e:
                logger.error(f"Error saving file for {key}: {e}")
                # 여기서는 예외를 발생시키지 않고 계속 진행합니다.
                continue

        logger.info("Translation and saving process completed successfully")
        return {"status": "success"}
    except Exception as e:
        logger.error(f"Unexpected error in main function: {e}")
        logger.error(traceback.format_exc())
        return {"status": "error", "message": str(e)}, 500

if __name__ == "__main__":
    # 테스트를 위한 샘플 데이터
    test_data = {"bucket": "test-bucket", "name": "test-file.srt"}
    result = main(test_data)
    print(result)
