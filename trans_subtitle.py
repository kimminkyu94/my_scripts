import os
from google.cloud import storage
import openai
import logging
import traceback

# 로깅 설정
logging.basicConfig(level=logging.INFO)

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
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": f"You are a professional translator and subtitle editor. Translate the following text to {target_language} and split it into two natural, readable lines if it's long. The translation should be natural and easy to read."},
                {"role": "user", "content": text}
            ]
        )
        translated_text = response.choices[0].message['content']
        # 유니코드 이스케이프 시퀀스 디코딩
        translated_text = translated_text.encode().decode('unicode_escape')
        
        # 줄바꿈을 기준으로 분리
        lines = translated_text.split('\n')
        
        # 한 줄이면 그대로 반환, 두 줄 이상이면 처음 두 줄만 반환
        if len(lines) == 1:
            return lines[0]
        else:
            return '\n'.join(lines[:2])
    except Exception as e:
        logging.error(f"Translation error: {str(e)}")
        return text  # 오류 발생 시 원본 텍스트 반환

def process_srt(content, target_language):
    lines = content.split('\n')
    translated_lines = []
    current_text = ""
    subtitle_index = 1

    for line in lines:
        if line.strip().isdigit():
            # 자막 번호
            translated_lines.append(str(subtitle_index))
            subtitle_index += 1
        elif '-->' in line:
            # 시간 정보
            translated_lines.append(line)
        elif line.strip():
            # 자막 텍스트 누적
            current_text += line.strip() + " "
        elif current_text:
            # 빈 줄을 만났을 때 번역 및 분할 수행
            translated_text = translate_and_split(current_text.strip(), target_language)
            translated_lines.extend(translated_text.split('\n'))
            translated_lines.append('')  # 자막 항목 사이의 빈 줄
            current_text = ""

    # 마지막 자막 처리
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
        source_blob = source_blob = source_bucket.blob(file_name)
        content = source_blob.download_as_text()

        # 유니코드 이스케이프 시퀀스 디코딩
        content = content.encode().decode('unicode_escape')

        target_bucket = storage_client.bucket("allcloudstorage3")

        results = []
        for lang, lang_name in LANGUAGES.items():
            translated_content = process_srt(content, lang_name)
            lang_folder = lang.lower()
            target_file_name = f"{lang_folder}/{os.path.basename(file_name)}"
            target_blob = target_bucket.blob(target_file_name)
            
            # UTF-8로 인코딩하여 저장
            target_blob.upload_from_string(translated_content.encode('utf-8').decode(), content_type="text/plain; charset=utf-8")
            
            results.append(f"Translated to {lang}: {target_file_name}")

        logging.info("Translation completed successfully")
        return {"message": "Translation complete", "details": results}
    except Exception as e:
        logging.error(f"Error in translation process: {str(e)}")
        logging.error(traceback.format_exc())
        return {"error": str(e)}, 500

if __name__ == "__main__":
    # 테스트용 샘플 데이터
    test_data = {
        "bucket": "allcloudstorage2",
        "file": "sample.srt"
    }
    result = main(test_data)
    print(result)
