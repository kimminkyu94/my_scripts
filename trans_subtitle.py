import logging
import requests
import json
import os
from google.cloud import storage
import re

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

API_KEY = os.environ.get('API_KEY') or os.environ.get('OPENAI_API_KEY')
if not API_KEY:
    raise ValueError("API 키가 설정되지 않았습니다. 환경 변수를 확인해주세요.")
logger.info(f"API 키 확인: {API_KEY[:5]}...")

GPT_API_URL = 'https://api.openai.com/v1/chat/completions'
logger.info(f"GPT API URL: {GPT_API_URL}")

def translate_content(content):
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }
    data = {
        "model": "gpt-3.5-turbo",
        "messages": [
            {"role": "system", "content": "You are a translator. Translate the given subtitle into Brazilian Portuguese, American English, Japanese, Thai, Indonesian, Vietnamese, Filipino, Malaysian, and Mexican Spanish. Return the results as a text with country names as headers."},
            {"role": "user", "content": content}
        ]
    }
    try:
        logger.info(f"Sending content to OpenAI GPT API: {GPT_API_URL}")
        response = requests.post(GPT_API_URL, headers=headers, json=data, timeout=30)
        response.raise_for_status()
        logger.info("OpenAI GPT API request successful")
        return response.json()['choices'][0]['message']['content']
    except requests.exceptions.RequestException as e:
        logger.error(f"Error calling OpenAI GPT API: {e}")
        raise

def parse_gpt_response(response):
    countries = re.findall(r'([A-Za-z\s]+):', response)
    subtitles = re.split(r'[A-Za-z\s]+:', response)[1:]
    return dict(zip(countries, subtitles))

def save_to_storage(bucket_name, country, content):
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(f"{country.lower().strip()}/subtitle.srt")
    blob.upload_from_string(content.strip(), content_type="text/plain; charset=utf-8")

def main(data):
    try:
        bucket_name = data['bucket']
        file_name = data['name']

        logger.info(f"Processing file: {file_name} from bucket: {bucket_name}")

        storage_client = storage.Client()
        bucket = storage_client.get_bucket(bucket_name)
        blob = bucket.blob(file_name)

        content = blob.download_as_string().decode('utf-8')
        logger.info(f"File content (first 100 chars): {content[:100]}...")

        translated_content = translate_content(content)
        logger.info(f"Raw translated content: {translated_content}")

        translations = parse_gpt_response(translated_content)
        logger.info(f"Translation successful. Languages: {list(translations.keys())}")

        output_bucket_name = "allcloudstorage3"

        for country, subtitle in translations.items():
            country_folder = country.lower().strip()
            if country_folder == "american english":
                country_folder = "america"
            elif country_folder == "brazilian portuguese":
                country_folder = "brazil"
            elif country_folder == "mexican spanish":
                country_folder = "mexico"
            
            save_to_storage(output_bucket_name, country_folder, subtitle)
            logger.info(f"Successfully saved file for {country} in folder {country_folder}")

        logger.info("Translation and saving process completed successfully")
        return {"status": "success"}
    except Exception as e:
        logger.error(f"Unexpected error in main function: {e}")
        return {"status": "error", "message": str(e)}, 500

if __name__ == "__main__":
    test_data = {"bucket": "test-bucket", "name": "test-file.srt"}
    result = main(test_data)
    print(result)
