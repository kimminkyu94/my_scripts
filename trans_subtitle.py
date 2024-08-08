import logging
import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from google.cloud import storage

# 로깅 설정
logging.basicConfig(level=logging.INFO)

app = FastAPI()

class Data(BaseModel):
    bucket: str
    name: str

@app.post("/trans_subtitle")
async def trans_subtitle(data: Data):
    bucket_name = data.bucket
    file_name = data.name

    storage_client = storage.Client()
    bucket = storage_client.get_bucket(bucket_name)
    blob = bucket.blob(file_name)

    try:
        logging.info(f"Downloading file: {file_name} from bucket: {bucket_name}")
        content = blob.download_as_string().decode('utf-8')
    except Exception as e:
        logging.error(f"Error downloading file: {e}")
        raise HTTPException(status_code=500, detail=f"Error downloading file: {e}")

    # 커스텀 GPT API URL
    GPT_API_URL = "https://chatgpt.com/g/g-3YjxJTJ4R-trans-srt"
    try:
        logging.info(f"Sending content to GPT API: {GPT_API_URL}")
        response = requests.post(GPT_API_URL, json={"content": content})
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        logging.error(f"Error calling GPT API: {e}")
        raise HTTPException(status_code=500, detail=f"Error calling GPT API: {e}")

    try:
        translated_content = response.json().get('processed_content')
        if not translated_content:
            raise ValueError('Translated content is empty')
    except Exception as e:
        logging.error(f"Error processing GPT response: {e}")
        raise HTTPException(status_code=500, detail=f"Error processing GPT response: {e}")

    # 번역된 내용을 파싱하여 각 나라별로 저장
    countries = ['Indonesia', 'Malaysia', 'Vietnam', 'Filipin', 'Japan', 'Thailand', 'Mexico', 'Brazil', 'America']
    output_bucket_name = "allcloudstorage3"
    output_bucket = storage_client.get_bucket(output_bucket_name)

    try:
        country_contents = extract_country_contents(translated_content, countries)
    except Exception as e:
        logging.error(f"Error extracting country contents: {e}")
        raise HTTPException(status_code=500, detail=f"Error extracting country contents: {e}")

    for country, content in country_contents.items():
        if content:
            try:
                logging.info(f"Saving translated file for {country} to bucket: {output_bucket_name}")
                output_blob = output_bucket.blob(f"{country}/{file_name}")
                output_blob.upload_from_string(content)
            except Exception as e:
                logging.error(f"Error saving file for {country}: {e}")
                raise HTTPException(status_code=500, detail=f"Error saving file for {country}: {e}")

    logging.info("Translation and saving process completed successfully")
    return {"status": "success"}

def extract_country_contents(content, countries):
    country_contents = {}
    current_country = None
    lines = content.split('\n')

    for line in lines:
        country_match = next((country for country in countries if line.startswith(f"{country}:")), None)
        if country_match:
            current_country = country_match
            country_contents[current_country] = ''
        elif current_country:
            country_contents[current_country] += line + '\n'

    for country in country_contents:
        country_contents[country] = country_contents[country].trim()

    return country_contents

