from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from typing import Optional
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os

app = FastAPI() # 建立Application

# CORS(跨來源資源共享)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # 允許來自http://localhost:3000 的請求
    allow_credentials=True,
    allow_methods=["*"],  # 允許所有 HTTP 方法（GET、POST、PUT 等）
    allow_headers=["*"],  # 允許所有自訂標頭
)

# 儲存檔案
AUDIO_OUTPUT_FILE = "output.wav"
if os.path.exists(AUDIO_OUTPUT_FILE): # 如果檔案存在，刪除
    os.remove(AUDIO_OUTPUT_FILE)

@app.websocket("/ws/audio")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_bytes()
            print(f"接收到 {len(data)} bytes 的音訊資料")
            with open(AUDIO_OUTPUT_FILE, "a", encoding="utf-8") as f:
                f.write(data + "\n")
    except WebSocketDisconnect:
        print("WebSocket Disconnected")


# 定義輸入資料的格式
class Message(BaseModel):
    text: str

@app.get("/")
def read_root():
    return {"Hello": "World"}

@app.post("/message")
async def save_message(message: Message):
    with open("message.txt", "a", encoding="utf-8") as f:
        f.write(message.text + "\n")
    
    return {"status": "ok"}