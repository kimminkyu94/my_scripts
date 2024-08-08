import logging
import requests
import json
import os
import traceback
from google.cloud import storage

# 로깅 설정
logging.basicConfig(level=logging.INFO)

# OpenAI API URL
GPT_API_URL = "https://api.openai.com/v1/completions"

# OpenAI API 키
OPENAI_API_KEY = 'sk-proj-oMBzy0gMEiyelCq7UaZtT3BlbkFJATMGu6zY4ZdH5u3HtU4n'

def main(data):
    try:
        bucket_name = data['bucket']
        file_name = data['name']

        storage_client = storage.Client()
        bucket = storage_client.get_bucket(bucket_name)
        blob = bucket.blob(file_name)

        try:
            logging.info(f"Downloading file: {file_name} from bucket: {bucket_name}")
            content = blob.download_as_string().decode('utf-8')
        except Exception as e:
            logging.error(f"Error downloading file: {e}")
            raise

        try:
            logging.info(f"Sending content to GPT API: {GPT_API_URL}")
            headers = {
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "Content-Type": "application/json"
            }
            data = {
                "model": "text-davinci-003",
                "prompt": f"Translate the following Korean subtitles into multiple languages:\n\n{content}",
                "max_tokens": 2048,
                "temperature": 0.5
            }
            response = requests.post(GPT_API_URL, headers=headers, json=data, timeout=30)
            response.raise_for_status()
            logging.info(f"GPT API raw response: {response.text}")
            
            try:
                response_json = response.json()
                translated_content = response_json.get('choices')[0].get('text')
                if not translated_content:
                    logging.error(f"No translated content in response: {response_json}")
                    raise ValueError('Translated content is empty or missing')
            except json.JSONDecodeError as e:
                logging.error(f"Error decoding GPT API response: {e}")
                logging.error(f"Raw response content: {response.text}")
                raise
        except requests.exceptions.RequestException as e:
            logging.error(f"Error calling GPT API: {e}")
            raise
        except ValueError as e:
            logging.error(f"Error processing GPT API response: {e}")
            raise

        # 번역된 내용을 파싱하여 각 나라별로 저장
        countries = ['Indonesia', 'Malaysia', 'Vietnam', 'Filipin', 'Japan', 'Thailand', 'Mexico', 'Brazil', 'AmericanEnglish']
        output_bucket_name = "allcloudstorage3"
        output_bucket = storage_client.get_bucket(output_bucket_name)

        try:
            country_contents = extract_country_contents(translated_content, countries)
        except Exception as e:
            logging.error(f"Error extracting country contents: {e}")
            raise

        for country, content in country_contents.items():
            if content:
                try:
                    logging.info(f"Saving translated file for {country} to bucket: {output_bucket_name}")
                    output_blob = output_bucket.blob(f"{country}/{file_name}")
                    output_blob.upload_from_string(content)
                except Exception as e:
                    logging.error(f"Error saving file for {country}: {e}")
                    raise

        logging.info("Translation and saving process completed successfully")
        return {"status": "success"}
    except Exception as e:
        logging.error(f"Unexpected error in main function: {e}")
        logging.error(traceback.format_exc())
        return {"status": "error", "message": str(e)}, 500

def extract_country_contents(content, countries):
    country_contents = {country: "" for country in countries}
    current_country = None
    lines = content.split('\n')

    for line in lines:
        country_match = next((country for country in countries if line.startswith(f"{country}:")), None)
        if country_match:
            current_country = country_match
        elif current_country:
            country_contents[current_country] += line + '\n'

    for country in country_contents:
        country_contents[country] = country_contents[country].strip()

    return country_contents

if __name__ == "__main__":
    # 테스트를 위한 샘플 데이터
    test_data = {"bucket": "test-bucket", "name": "test-file.srt"}
    result = main(test_data)
    print(result)

