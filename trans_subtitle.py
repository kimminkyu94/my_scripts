import logging
import requests
import json
import os
from google.cloud import storage
import traceback

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

API_KEY = os.environ.get('API_KEY') or os.environ.get('OPENAI_API_KEY')
if not API_KEY:
    raise ValueError("API 키가 설정되지 않았습니다. 환경 변수를 확인해주세요.")
logger.info(f"API 키 확인: {API_KEY[:5]}...")

GPT_API_URL = 'https://api.openai.com/v1/chat/completions'
logger.info(f"GPT API URL: {GPT_API_URL}")

LANGUAGES = ['japan', 'thailand', 'indonesia', 'vietnam', 'filipin', 'malaysia', 'brazil', 'mexico']

def translate_content(content):
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }
    data = {
        "model": "gpt-3.5-turbo",
        "messages": [
            {"role": "system", "content": "You are a translator. Translate the given subtitle into Japanese, Thai, Indonesian, Vietnamese, Filipino, Malaysian, Brazilian Portuguese, and Mexican Spanish. Return the results as a JSON object with country names as keys."},
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

def format_to_srt(subtitles_json):
    formatted_subtitle = ""
    for index, (timecode, text) in enumerate(subtitles_json.items(), start=1):
        formatted_subtitle += f"{index}\n{timecode}\n{text}\n\n"
    return formatted_subtitle

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

        translated_contents = translate_content(content)
        if not translated_contents or 'choices' not in translated_contents:
            raise ValueError('Translated content is empty or missing')
        
        translations = json.loads(translated_contents['choices'][0]['message']['content'])

        logger.info(f"Translation successful. Languages: {list(translations.keys())}")

        output_bucket_name = "allcloudstorage3"
        output_bucket = storage_client.get_bucket(output_bucket_name)

        for country, translated_content in translations.items():
            try:
                country_folder = next((lang for lang in LANGUAGES if lang in country.lower()), 'other')
                logger.info(f"Saving translated file for {country} to bucket: {output_bucket_name}/{country_folder}")

                # Convert the dictionary to the SRT format
                translated_content_srt = format_to_srt(translated_content)
                
                output_blob = output_bucket.blob(f"{country_folder}/{file_name}")
                output_blob.upload_from_string(translated_content_srt)
                logger.info(f"Successfully saved file for {country}")
            except Exception as e:
                logger.error(f"Error saving file for {country}: {e}")
                continue

        logger.info("Translation and saving process completed successfully")
        return {"status": "success"}
    except Exception as e:
        logger.error(f"Unexpected error in main function: {e}")
        logger.error(traceback.format_exc())
        return {"status": "error", "message": str(e)}, 500

if __name__ == "__main__":
    test_data = {"bucket": "test-bucket", "name": "test-file.srt"}
    result = main(test_data)
    print(result)
