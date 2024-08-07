import os
import openai
import logging
import traceback
import unicodedata
from google.cloud import storage

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# OpenAI API 키 설정
openai.api_key = os.getenv('OPENAI_API_KEY')

LANGUAGES = {
    "Indonesia": "Indonesian",
    "Malaysia": "Malay",
    "Vietnam": "Vietnamese",
    "Filipin": "Filipino",
    "Japan": "Japanese",
    "Thailand": "Thai",
    "Mexico": "Spanish",
    "Brazil": "Portuguese",
    "America": "English"
}

def translate_and_split(text, target_language):
    try:
        logging.info(f"Translating to {target_language}: {text[:50]}...")  # 처음 50자만 로그
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": f"Translate the following subtitle text to {target_language}. If the translation is long, split it into two natural sentences. Maintain the original meaning and style."},
                {"role": "user", "content": text}
            ]
        )
        translated_text = response.choices[0].message['content']
        translated_text = unicodedata.normalize('NFC', translated_text)  # 유니코드 정규화
        
        # 문장을 두 개로 나누기
        sentences = translated_text.split('.')
        if len(sentences) > 1:
            first_part = sentences[0].strip() + '.'
            second_part = '.'.join(sentences[1:]).strip()
            result = f"{first_part}\n{second_part}"
        else:
            result = translated_text
        
        logging.info(f"Translation result for {target_language}: {result[:100]}...")  # 처음 100자만 로그
        return result
    except Exception as e:
        logging.error(f"Translation error for {target_language}: {str(e)}")
        return text

def process_srt(content, target_language):
    lines = content.split('\n')
    translated_lines = []
    current_text = ""
    subtitle_index = 1

    for line in lines:
        if line.strip().isdigit():
            translated_lines.append(str(subtitle_index))
            subtitle_index += 1
        elif '-->' in line:
            translated_lines.append(line)
        elif line.strip():
            current_text += line.strip() + " "
        elif current_text:
            logging.info(f"Processing subtitle text: {current_text[:50]}...")  # 처음 50자만 로그
            translated_text = translate_and_split(current_text.strip(), target_language)
            translated_lines.extend(translated_text.split('\n'))
            translated_lines.append('')
            current_text = ""

    if current_text:
        translated_text = translate_and_split(current_text.strip(), target_language)
        translated_lines.extend(translated_text.split('\n'))

    return '\n'.join(translated_lines)

def main(data):
    bucket_name = data['bucket']
    file_name = data['file']

    logging.info(f"Processing file: {file_name} from bucket: {bucket_name}")

    try:
        storage_client = storage.Client()
        source_bucket = storage_client.bucket(bucket_name)
        source_blob = source_bucket.blob(file_name)
        
        # UTF-8로 명시적으로 읽기
        content = source_blob.download_as_text(encoding='utf-8')
        
        # 유니코드 정규화
        content = unicodedata.normalize('NFC', content)

        target_bucket = storage_client.bucket("allcloudstorage3")

        results = []
        for lang, lang_name in LANGUAGES.items():
            try:
                translated_content = process_srt(content, lang_name)
                lang_folder = lang.lower()
                target_file_name = f"{lang_folder}/{os.path.basename(file_name)}"
                target_blob = target_bucket.blob(target_file_name)
                
                # UTF-8로 명시적으로 저장
                target_blob.upload_from_string(translated_content, content_type="text/plain; charset=utf-8")
                
                results.append(f"Translated to {lang}: {target_file_name}")
                logging.info(f"Successfully translated and saved {lang} subtitles")
            except Exception as e:
                error_msg = f"Error translating to {lang}: {str(e)}"
                logging.error(error_msg)
                results.append(error_msg)

        logging.info("Translation process completed")
        return {"message": "Translation complete", "details": results}
    except Exception as e:
        error_msg = f"Error in translation process: {str(e)}"
        logging.error(error_msg)
        logging.error(traceback.format_exc())
        return {"error": error_msg}, 500

if __name__ == "__main__":
    # 테스트용 샘플 데이터
    test_data = {
        "bucket": "allcloudstorage2",
        "file": "sample.srt"
    }
    result = main(test_data)
    print(result)
