import webrtcvad
import wave
import os
import noisereduce as nr
import soundfile as sf
from function import merge_audio_files

def process_audio_file(input_path, output_dir_path):
    # 先進行降噪處理
    audio, sample_rate = sf.read(input_path)
    reduced_noise = nr.reduce_noise(y=audio, sr=sample_rate, prop_decrease=0.9)  # 增加降噪強度
    sf.write("reduced_noise.wav", reduced_noise, sample_rate)
    
    vad = webrtcvad.Vad()
    vad.set_mode(1)  # 調整模式以適應您的音頻環境
    
    with wave.open("reduced_noise.wav", 'rb') as wav_file:
        if(wav_file.getnchannels() != 1 or wav_file.getsampwidth() != 2 or wav_file.getframerate() != 16000):
            raise ValueError("Invalid WAV file format")
        
        sample_rate = wav_file.getframerate()
        frames = wav_file.readframes(wav_file.getnframes())
        
        frame_duration_ms = 20  # 調整幀持續時間
        bytes_per_sample = 2
        samples_per_frame = int(sample_rate * frame_duration_ms // 1000)
        frame_size = samples_per_frame * bytes_per_sample
        
        start_byte = 0
        vad_segments = []
        active_count = 0
        inactive_count = 0
        last_cut = 0
        start = False
        
        while start_byte + frame_size < len(frames):
            end_byte = min(start_byte + frame_size, len(frames))
            frame_bytes = frames[start_byte:end_byte]
            
            if not vad.is_speech(frame_bytes, sample_rate):
                inactive_count += 1
                active_count = 0
            else:
                inactive_count = 0
                if not start and active_count < 20:
                    active_count += 1
                else:
                    start = True

            if inactive_count == 20 and start:
                vad_segments.append((last_cut, start_byte))
                last_cut = start_byte
                start = False
                active_count = 0
            
            start_byte += frame_size
        
        if start:
            vad_segments.append((last_cut, len(frames)))
        
        for i, seg in enumerate(vad_segments):
            segment = frames[seg[0]:seg[1]]
            output_file = os.path.join(output_dir_path, f"segment_{i + 1}.wav")
            with wave.open(output_file, 'wb') as f:
                f.setnchannels(1)
                f.setsampwidth(2)
                f.setframerate(16000)
                f.writeframes(segment)
        
        return vad_segments

class AudioStream:
    def __init__(self):
        self.active_count = 0
        self.inactive_count = 0
        self.start = False
        self.left_bytes = bytearray()
        self.sentence_count = 0
        self.buffer = bytearray()
        self.last_cut = 0
        
    def streaming_sentence_detector(self, frame_bytes, sample_rate, output_dir_path):
        vad = webrtcvad.Vad()
        vad.set_mode(2) # 0 ~ 3
        
        frame_duration_ms = 20 # 20ms
        bytes_per_sample = 2 # 2 bytes
        samples_per_frame = int(sample_rate * frame_duration_ms // 1000) # 16000 * 20 / 1000 = 320
        frame_size = samples_per_frame * bytes_per_sample # 320 * 2 = 640
        
        start_byte = 0
        have_sentence_end = False
        
        # 將上次剩餘的bytes與新的frame_bytes合併
        self.buffer.extend(frame_bytes)
        
        total_length = len(self.buffer)
        start_byte = self.last_cut
        
        while start_byte + frame_size <= total_length:
            current_frame = self.buffer[start_byte:start_byte + frame_size]
            
            if not vad.is_speech(current_frame, sample_rate):
                # print("not speaking")
                self.inactive_count += 1
                self.active_count = 0
            else:
                # print("speaking")
                self.inactive_count = 0
                if not self.start and self.active_count < 25:
                    self.active_count += 1
                else:
                    self.start = True 
            
            if self.inactive_count == 25 and self.start:
                # print("sentence end")
                
                segment_data = self.buffer[self.last_cut:start_byte]
                if segment_data:
                    self.sentence_count += 1
                    output_file = f"{output_dir_path}/sentence_{self.sentence_count}.wav"
                    with wave.open(output_file, 'wb') as f:
                        f.setnchannels(1)
                        f.setsampwidth(2)
                        f.setframerate(16000)
                        f.writeframes(segment_data)
                
                self.start = False
                self.inactive_count = 0
                self.active_count = 0
                self.last_cut = start_byte + frame_size
                have_sentence_end = True
                
            start_byte += frame_size
        
        if self.last_cut > 0:
            self.buffer = self.buffer[self.last_cut:]
            self.last_cut = 0
        return have_sentence_end
    
class AudioStream2:
    def __init__(self):
        self.count = 1
        
    def streaming_sentence_detector(self, input_path, output_dir_path):
        vad = webrtcvad.Vad()
        vad.set_mode(1) # 0 ~ 3
        
        with wave.open(input_path, 'rb') as wav_file:
            
            if(wav_file.getnchannels() != 1 or wav_file.getsampwidth() != 2 or wav_file.getframerate() != 16000):
                raise ValueError("Invalid WAV file format")
            
            sample_rate = wav_file.getframerate() # 16000
            frames = wav_file.readframes(wav_file.getnframes()) # 16000 * 2 * 20
            
            frame_duration_ms = 20 # 20ms
            bytes_per_sample = 2 # 2 bytes
            samples_per_frame = int(sample_rate * frame_duration_ms // 1000) # 16000 * 20 / 1000 = 320
            frame_size = samples_per_frame * bytes_per_sample # 320 * 2 = 640
            
            start_byte = 0
            vad_segments = []
            active_count = 0
            inactive_count = 0
            last_cut = 0
            start = False
            
            # 每20ms進行一次VAD(Voice Activity Detection)
            while start_byte + frame_size < len(frames):
                end_byte = min(start_byte + frame_size, len(frames))
                frame_bytes = frames[start_byte:end_byte] # 獲得這30ms的音檔
                
                # 若空白音檔持續至少約300ms，則紀錄起來
                if not vad.is_speech(frame_bytes, sample_rate):
                    # print("not speaking")
                    inactive_count += 1
                    active_count = 0
                else:
                    # print("speaking")
                    inactive_count = 0
                    if not start and active_count < 25:
                        active_count += 1
                    else:
                        start = True

                if inactive_count == 25 and start:
                    vad_segments.append((last_cut, start_byte))
                    last_cut = start_byte
                    start = False
                    active_count = 0
                
                # 下一段音檔
                start_byte += frame_size
            
            output_file = os.path.join(output_dir_path, f"segment.wav")
            if os.path.exists(output_file):
                os.remove(output_file)
            
            # 若最後一段音檔是空白音檔，則不加入
            if start:
                segment = frames[last_cut:len(frames)]
                with wave.open(output_file, 'wb') as f:
                    f.setnchannels(1)
                    f.setsampwidth(2)
                    f.setframerate(16000)
                    f.writeframes(segment)
                return True
            
            elif not os.path.exists(output_file) and len(vad_segments) > 0:
                segment = frames[vad_segments[-1][0]:vad_segments[-1][1]]
                with wave.open(output_file, 'wb') as f:
                    f.setnchannels(1)
                    f.setsampwidth(2)
                    f.setframerate(16000)
                    f.writeframes(segment)
                
                self.count += 1
                return True
                
                
# input_path = "./voice_output.wav"
# output_dir_path = "./output_segments"
# segments = process_audio_file(input_path, output_dir_path)
# for seg in segments:
#     start_time = (seg[0] // 2) / 16000
#     end_time = (seg[1] // 2) / 16000
#     print(f'segment from {start_time:.2f} to {end_time:.2f} seconds')