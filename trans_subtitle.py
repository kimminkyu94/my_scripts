# trans_subtitle.py

import os
from google.cloud import storage
import openai

# OpenAI API 키 설정 (환경 변수에서 가져오기)
openai.api_key = os.getenv("OPENAI_API_KEY")

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

def split_long_lines(text):
    words = text.split()
    if len(words) > 7:  # 7단어 이상이면 분할
        mid = len(words) // 2
        return ' '.join(words[:mid]) + '\n' + ' '.join(words[mid:])
    return text

def translate_text(text, target_language):
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": f"You are a professional translator. Translate the following text to {target_language}. The translation should be natural and easy to read. If the input is two lines, maintain a two-line structure in the output."},
            {"role": "user", "content": text}
        ]
    )
    return response.choices[0].message['content']

def process_srt(content, target_language):
    lines = content.split('\n')
    translated_lines = []
    current_text = ""

    for line in lines:
        if line.strip().isdigit() or '-->' in line:
            translated_lines.append(line)
        elif line.strip():
            current_text += line.strip() + " "
        elif current_text:
            current_text = split_long_lines(current_text.strip())
            translated_text = translate_text(current_text, target_language)
            translated_lines.extend(translated_text.split('\n'))
            translated_lines.append('')
            current_text = ""

    if current_text:
        current_text = split_long_lines(current_text.strip())
        translated_text = translate_text(current_text, target_language)
        translated_lines.extend(translated_text.split('\n'))

    return '\n'.join(translated_lines)

def main(data):
    bucket_name = data['bucket']
    file_name = data['file']

    storage_client = storage.Client()
    source_bucket = storage_client.bucket(bucket_name)
    source_blob = source_bucket.blob(file_name)
    content = source_blob.download_as_text()

    target_bucket = storage_client.bucket("allcloudstorage3")

    results = []
    for lang, lang_name in LANGUAGES.items():
        translated_content = process_srt(content, lang_name)
        lang_folder = lang.lower()
        target_file_name = f"{lang_folder}/{os.path.basename(file_name)}"
        target_blob = target_bucket.blob(target_file_name)
        target_blob.upload_from_string(translated_content)
        results.append(f"Translated to {lang}: {target_file_name}")

    return {"message": "Translation complete", "details": results}

# 이 부분은 로컬 테스트를 위한 것이며, Cloud Run에서는 사용되지 않습니다.
if __name__ == "__main__":
    # 로컬 테스트를 위한 샘플 데이터
    test_data = {
        "bucket": "allcloudstorage2",
        "file": "sample.srt"
    }
    result = main(test_data)
    print(result)
