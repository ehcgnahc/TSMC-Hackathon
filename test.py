import os
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from typing import AsyncGenerator
from fastapi.middleware.cors import CORSMiddleware
# from google.cloud import speech
# from google.oauth2 import service_account

# client_file = "google-credentials.json" # GCP服務帳戶金鑰
# credentials = service_account.Credentials.from_service_account_file(client_file) # 讀取金鑰並建立Credentials (用於GCP API呼叫的認證物件)
# client = speech.SpeechClient(credentials=credentials) # 建立SpeechClient (可直接呼叫STT API)
app = FastAPI() # 建立Application

# CORS(跨來源資源共享)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # 允許來自react的請求
    allow_credentials=True,
    allow_methods=["*"],  # 允許所有 HTTP 方法（GET、POST、PUT 等）
    allow_headers=["*"],  # 允許所有自訂標頭
)

# 從WebSocket連線 持續接收音訊chunk
async def receive_audio_chunks(websocket: WebSocket) -> AsyncGenerator[bytes, None]:
    try:
        while True:
            data = await websocket.receive_bytes()
            yield data
    except WebSocketDisconnect:
        print("WebSocket Disconnected")
    except Exception as e:
        print(e)

# 透過WebSocket接收音訊資料
@app.websocket("/ws/audio")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    voice_path = "voice_output.wav"
    
    # 刪除舊檔
    if os.path.exists(voice_path):
        os.remove(voice_path)
    
    with open(voice_path, "wb") as f:
        async for chunk in receive_audio_chunks(websocket):
            print(f"receive {len(chunk)} bytes") # 顯示接收到的資料長度
            f.write(chunk) # 寫入檔案

    print("Finish Receiving Audio")
    await websocket.close()