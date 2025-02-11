import pyaudio
from google.cloud import speech
from google.oauth2 import service_account

# 建立 Google Speech API 客戶端
client_file = "google-credentials.json"  # 請確認此檔案存在並有效
credentials = service_account.Credentials.from_service_account_file(client_file)
client = speech.SpeechClient(credentials=credentials)

def audio_generator():
    """
    利用 pyaudio 從麥克風持續捕捉音訊數據，
    並以生成器的方式 yield 出每個固定大小的音訊 chunk。
    """
    pa = pyaudio.PyAudio()
    stream = pa.open(
        format=pyaudio.paInt16,
        channels=1,  # 使用單聲道錄音
        rate=16000,
        input=True,
        frames_per_buffer=160
    )
    try:
        while True:
            data = stream.read(160) # 型態: bytes
            yield data
    finally:

        stream.stop_stream()
        stream.close()
        pa.terminate()

# 建立 StreamingRecognitionConfig 配置
config = speech.RecognitionConfig(
    encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
    sample_rate_hertz=16000,
    language_code="en-US",
    alternative_language_codes=["zh-TW", "ja-JP", "de-DE"]
)
streaming_config = speech.StreamingRecognitionConfig(
    config=config,
    interim_results=True  # 允許回傳中間結果
)

# 音訊 chunk 包裝成 Google API 需要的請求物件
requests = (
    speech.StreamingRecognizeRequest(audio_content=chunk)
    for chunk in audio_generator()
)

# 呼叫 streaming_recognize 方法進行即時語音辨識
responses = client.streaming_recognize(streaming_config, requests)

# 迭代回傳的 responses 並印出轉錄文字
for response in responses:
    for result in response.results:
        if result.alternatives:
            print("Transcript:", result.alternatives[0].transcript)
