import logging
import requests
import json
import os
from google.cloud import storage

# 로깅 설정
logging.basicConfig(level=logging.INFO)

# 커스텀 GPT API URL
GPT_API_URL = "https://subtitle-service-22hpg2idaq-uc.a.run.app/translate"

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
            logging.info(f"Sending content to Custom GPT API: {GPT_API_URL}")
            headers = {
                "Content-Type": "application/json"
                # 필요한 경우 인증 헤더 추가
            }
            data = {
                "content": content
            }
            response = requests.post(GPT_API_URL, headers=headers, json=data, timeout=30)
            response.raise_for_status()
            logging.info(f"Custom GPT API raw response: {response.text}")
            
            try:
                translated_contents = response.json()
                if not translated_contents:
                    logging.error(f"No translated content in response: {translated_contents}")
                    raise ValueError('Translated content is empty or missing')
            except json.JSONDecodeError as e:
                logging.error(f"Error decoding Custom GPT API response: {e}")
                logging.error(f"Raw response content: {response.text}")
                raise
        except requests.exceptions.RequestException as e:
            logging.error(f"Error calling Custom GPT API: {e}")
            raise
        except ValueError as e:
            logging.error(f"Error processing Custom GPT API response: {e}")
            raise

        output_bucket_name = "allcloudstorage3"
        output_bucket = storage_client.get_bucket(output_bucket_name)

        for country, content in translated_contents.items():
            if content:
                try:
                    logging.info(f"Saving translated file for {country} to bucket: {output_bucket_name}")
                    output_blob = output_bucket.blob(f"{country}/{file_name}")
                    output_blob.upload_from_string("\n".join(content))
                except Exception as e:
                    logging.error(f"Error saving file for {country}: {e}")
                    raise

        logging.info("Translation and saving process completed successfully")
        return {"status": "success"}
    except Exception as e:
        logging.error(f"Unexpected error in main function: {e}")
        logging.error(traceback.format_exc())
        return {"status": "error", "message": str(e)}, 500

if __name__ == "__main__":
    # 테스트를 위한 샘플 데이터
    test_data = {"bucket": "test-bucket", "name": "test-file.srt"}
    result = main(test_data)
    print(result)
