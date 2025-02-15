import os
import time
import shutil
import json
import deepl
from openai import OpenAI
from fastapi import FastAPI, UploadFile, File, HTTPException, WebSocket, WebSocketDisconnect 
from fastapi.middleware.cors import CORSMiddleware
from Stt import STT, meeting_translator, LANGUAGES
from process_audio import process_audio_file, AudioStream2
from function import get_keywords, merge_audio_files, get_audio_info, reduce_noise, isolate_voice, save_as_wav, save_to_wav
from Key import OpenAI_API_KEY, DEEPL_API_KEY
from Stt import get_keywords_from_dict, get_keywords_dictionary, pattern_finder

openai_client = OpenAI(api_key=OpenAI_API_KEY)
deepl_client = deepl.Translator(DEEPL_API_KEY)
translator_meeting = meeting_translator(openai_client, deepl_client)

app = FastAPI()

# CORS(跨來源資源共享)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],  # 允許來自react的請求
    allow_credentials=True,
    allow_methods=["*"],  # 允許所有 HTTP 方法（GET、POST、PUT 等）
    allow_headers=["*"],  # 允許所有自訂標頭
)

def save_chinese_translation(text, filename="chinese_translation.txt"):
    try:
        # 使用 'a' 模式來追加內容而不是覆蓋
        with open(filename, 'a', encoding='utf-8') as file:
            file.write(text + '\n')  # 每次寫入後換行
        # print(f"翻譯已成功追加到 {filename}")
    except Exception as e:
        print(f"儲存文件時發生錯誤：{str(e)}")

def save_keywords(keywords, filename="keywords.txt"):
    try:
        # 使用 'a' 模式來追加內容而不是覆蓋
        with open(filename, 'a', encoding='utf-8') as file:
            for keyword in keywords:
                file.write(keyword + '\n')  # 每個關鍵字寫入後換行
        print(f"關鍵字已成功追加到 {filename}")
    except Exception as e:
        print(f"儲存關鍵字時發生錯誤：{str(e)}")

# 使用示例
# chinese_text = "這是一個測試文本。這裡可以放入你的中文翻譯。"
# save_chinese_translation(chinese_text)

@app.websocket("/ws/upload")
async def upload_audio(websocket: WebSocket):
    try:
        await websocket.accept()
        
        original = []
        chinese = []
        english = []
        japan = []
        german = []
        
        voice_input_path = "voice_input.wav"
        voice_path_wav = "voice_output.wav"
        output_dir_path = "./upload_output_segments"
        
        time_start = time.time()
        
        # 清理輸出目錄
        if os.path.exists(output_dir_path):
            shutil.rmtree(output_dir_path)
        os.makedirs(output_dir_path)
        
        # 初始化 STT 模型
        stt_model = STT(openai_client, keywords=get_keywords())
        
        # 獲取關鍵字字典
        keyword_dict, _ = get_keywords_dictionary()

        # 初始化 pattern_finder
        keyword_finder = pattern_finder(keyword_dict)
        
        # 初始化一個集合來存儲所有檢測到的關鍵字
        all_detected_keywords = set()
        
        try:
            # 接收音頻文件
            content = await websocket.receive_bytes()
            
            # print('input_bytes length:', len(content))
            
            # 保存音頻文件
            with open(voice_input_path, "wb") as f_out:
                f_out.write(content)
            print(f"Received file, size = {len(content)} bytes")
            
            # 處理音頻
            merge_audio_files(voice_input_path, voice_path_wav)
            segments = process_audio_file(voice_path_wav, output_dir_path)
            
            print(segments)
            
            main_transcript = []
            
            if os.path.exists("chinese_translation.txt"):
                os.remove("chinese_translation.txt")
            
            # 處理每個片段
            for segment_file in sorted(os.listdir(output_dir_path), key=lambda x: int(x.split("_")[1].split(".")[0])):
                segment_path = os.path.join(output_dir_path, segment_file)
                
                with open(segment_path, "rb") as f:
                    segment_text = stt_model.transcript(f)
                    print(segment_text)
                    
                    source_language = translator_meeting._language_detector.detect_language_text(segment_text)
                    chinese_translation = translator_meeting.translate_by_text(
                        segment_text,
                        source_language=source_language,
                        target_language=LANGUAGES.TAIWANESE.value
                    )
                    translator_meeting.__make_keyword_output__(translator_meeting._keyword_finder.find_pattern(segment_text, source_language), translator_meeting._num_dict, source_language)
                    
                    original.append(segment_text)
                    chinese.append(chinese_translation)
                    
                    # 檢測關鍵字
                    detected_keywords = keyword_finder.find_pattern(segment_text, source_language)
                    
                    # 將檢測到的關鍵字添加到集合中
                    all_detected_keywords.update(detected_keywords)
                    
                    # 發送翻譯結果
                    main_transcript.append(chinese_translation)
                    save_chinese_translation(chinese_translation)
                    await websocket.send_json(main_transcript)

            for i, text in enumerate(original):
                english_translation = translator_meeting.translate_by_text(
                    text,
                    source_language=source_language,
                    target_language=LANGUAGES.ENGLISH.value
                )
                japanese_translation = translator_meeting.translate_by_text(
                    text,
                    source_language=source_language,
                    target_language=LANGUAGES.JAPANESE.value
                )
                german_translation = translator_meeting.translate_by_text(
                    text,
                    source_language=source_language,
                    target_language=LANGUAGES.GERMAN.value
                )
            
                english.append(english_translation)
                japan.append(japanese_translation)
                german.append(german_translation)

            # 保存所有檢測到的關鍵字
            save_keywords(all_detected_keywords)

            # 發送關鍵字結果
            await websocket.send_json({
                "event": "keywords",
                "keywords": list(all_detected_keywords)
            })
            
            # 只在最後發送一次完整的翻譯結果
            time_end = time.time()
            runtime = time_end-time_start
            await websocket.send_json({
                "event": "complete",
                "translations": {
                    # "original": original,
                    "chinese": chinese,
                    "english": english,
                    "japan": japan,
                    "german": german
                },
                "runtime": runtime
            })
            
            print(f"Program runtime {runtime//60} minutes, {runtime%60} seconds")
            
        except Exception as e:
            print(f"Error processing audio: {e}")
            await websocket.send_json({
                "event": "error",
                "error": str(e)
            })
            
    except WebSocketDisconnect:
        print("Client disconnected")
    finally:
        await websocket.close()

@app.websocket("/ws/stream")
async def websocket_endpoint(websocket: WebSocket):
    try:
        await websocket.accept()
        
        # 初始化 STT 模型
        stt_model = STT(openai_client, keywords=get_keywords())
        audio_chunks = []
        accumulated_size = 0
        max_chunk_size = 32000       
        buffer = b''
        
        save_transcript = False
        all_transcript = []
        
        audio_stream = AudioStream2()
        
        output_dir_path = "./ws_output_segments"
        if os.path.exists(output_dir_path):
            shutil.rmtree(output_dir_path)
            os.makedirs(output_dir_path)
        
        while True:
            try:
                # 接收音頻
                audio_chunk = await websocket.receive_bytes()
                print(f"Received audio chunk of size {len(audio_chunk)} bytes")
                
                if len(audio_chunk) == 0:
                    print("Received empty chunk, skipping")
                    continue
                # 將audio_chunk判斷是否包含斷句
                # print(audio_stream.streaming_sentence_detector(audio_chunk, 16000, output_dir_path))
                    
                buffer += audio_chunk
                audio_chunks.append(audio_chunk)
                accumulated_size += len(audio_chunk)
                
                print(f"Accumulated size: {accumulated_size}")
                
                if accumulated_size >= max_chunk_size:
                    start_time = time.time()
                    
                    complete_audio = buffer
                    if os.path.exists("complete_audio.wav"):
                        os.remove("complete_audio.wav")
                        
                    with open("complete_audio.wav", "wb") as f:
                        f.write(complete_audio)
                    
                    # save_to_wav(complete_audio, "complete_audio.wav")
                    
                    # isolated_dir = "isolated_audio"
                    # os.makedirs(isolated_dir, exist_ok=True)
                    
                    # vocals_path = isolate_voice("complete_audio.wav", isolated_dir)
                    
                    if os.path.exists("complete_output_audio.wav"):
                        os.remove("complete_output_audio.wav")
                    
                    merge_audio_files("complete_audio.wav", "complete_output_audio.wav")
                    
                    save_transcript = audio_stream.streaming_sentence_detector("complete_output_audio.wav", output_dir_path)
                    
                    print(save_transcript)
                    
                    # STT
                    try:
                        if os.path.exists("./ws_output_segments/segment.wav"):
                            with open("./ws_output_segments/segment.wav", "rb") as f:
                                transcript = stt_model.transcript(f)
                            
                            end_time = time.time()
                            runtime = end_time - start_time
                            print(f"Transcript: {all_transcript}, Runtime = {runtime}")
                            source_language = translator_meeting._language_detector.detect_language_text(transcript)
                            
                            chinese_translation = translator_meeting.translate_by_text(
                                transcript,
                                source_language=source_language,
                                target_language=LANGUAGES.TAIWANESE.value
                            )
                                # english_translation = translator_meeting.translate_by_text(
                                #     transcript,
                                #     source_language=source_language,
                                #     target_language=LANGUAGES.ENGLISH.value
                                # )
                                # japanese_translation = translator_meeting.translate_by_text(
                                #     transcript,
                                #     source_language=source_language,
                                #     target_language=LANGUAGES.JAPANESE.value
                                # )
                                # german_translation = translator_meeting.translate_by_text(
                                #     transcript,
                                #     source_language=source_language,
                                #     target_language=LANGUAGES.GERMAN.value
                                # )
                                
                            if save_transcript == True:
                                all_transcript.append(chinese_translation)
                                response_data = {
                                    "type": "SET_TRANSLATIONS",
                                    "value": {
                                        "transcript": all_transcript,
                                        "runtime": runtime
                                    }
                                }
                            else:
                                response_data = {
                                    "type": "SET_TRANSLATIONS",
                                    "value": {
                                        "transcript": all_transcript + [chinese_translation],
                                        "runtime": runtime
                                    }
                                }
                                
                            await websocket.send_text(json.dumps(response_data))
                    except Exception as e:
                        print(f"Error transcribing audio: {e}")
                        await websocket.send_text(f"Error: {str(e)}")
                    
                    # 重置
                    accumulated_size = 0
                
            except WebSocketDisconnect:
                print("WebSocket disconnected")
                break
            except Exception as e:
                print(f"Error processing chunk: {str(e)}")
                await websocket.send_text(f"Error: {str(e)}")
                
    except Exception as e:
        print(f"WebSocket error: {str(e)}")
    finally:
        try:
            await websocket.close()
        except:
            pass