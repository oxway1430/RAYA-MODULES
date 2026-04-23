
import speech_recognition as sr
import requests
import re
import os
import pygame
import time
import threading
import subprocess
from gtts import gTTS
from database_manager import RayaDB
from raya_processor import TokenProcessor
import face8

def get_working_mic_index():
    try:
        mics = sr.Microphone.list_microphone_names()
        for i, name in enumerate(mics):
            if "USB" in name or "WEBCAM" in name.upper() or "C270" in name:
                return i
        return None
    except:
        return None

WORKING_MIC_INDEX = get_working_mic_index()

def play_beep():
    if os.name == 'nt':
        try:
            import winsound
            winsound.Beep(900, 150)
        except:
            pass
    else:
        if not os.path.exists("beep.wav"):
            import wave, struct, math
            sample_rate, duration, frequency = 44100, 0.15, 900
            with wave.open("beep.wav", 'w') as obj:
                obj.setnchannels(1)
                obj.setsampwidth(2)
                obj.setframerate(sample_rate)
                for i in range(int(sample_rate * duration)):
                    value = int(32767.0 * math.sin(frequency * math.pi * float(i) / float(sample_rate)))
                    obj.writeframesraw(struct.pack('<h', value))
        os.system("aplay -q beep.wav 2>/dev/null")

SARVAM_API_KEY = "sk_69cwz5sk_AQe0riLTCMJplbOTi5VesCsi"
# SET YOUR PRINTER NAME HERE (e.g., "HP DeskJet 2700" or "\\\\SERVER\\PrinterName")
# Leave as None to use the default system printer
PRINTER_NAME = None

recognizer = sr.Recognizer()
db = RayaDB()
processor = TokenProcessor()

def open_file(path):
    """Linux aur Windows dono ke liye file opener"""
    try:
        if os.name == 'nt': # Windows
            os.startfile(os.path.abspath(path))
        else: # Raspberry Pi / Linux
            subprocess.run(['xdg-open', os.path.abspath(path)], check=True)
    except Exception as e:
        print(f"File Open Error: {e}")

def print_file(path):
    """Auto print tokens seamlessly on Linux (Raspberry Pi) and Windows"""
    try:
        if os.name == 'nt':
            if PRINTER_NAME:
                import win32api
                win32api.ShellExecute(0, "printto", os.path.abspath(path), f'"{PRINTER_NAME}"', ".", 0)
            else:
                os.startfile(os.path.abspath(path), "print")
        else:
            if PRINTER_NAME:
                subprocess.run(['lp', '-d', PRINTER_NAME, os.path.abspath(path)], check=True)
            else:
                try:
                    res = subprocess.run(['lp', os.path.abspath(path)], capture_output=True, text=True)
                    if res.stdout.strip(): print(res.stdout.strip())
                    if res.returncode != 0:
                        open_file(path)
                    else:
                        time.sleep(1.5)
                        lpq = subprocess.run(['lpq'], capture_output=True, text=True).stdout.lower()
                        if "not ready" in lpq or "offline" in lpq or "unplugged" in lpq or "wait" in lpq:
                            print("Printer seems offline. Opening PDF directly.")
                            open_file(path)
                except:
                    open_file(path)
    except ImportError:
        print("To print to a specific printer on Windows, please open terminal and run: pip install pywin32")
    except Exception as e:
        print(f"Print Error: {e}")
        open_file(path)

def speak(text, lang_code='hi'):
    """RAYA ki voice generator (voice.mp3)"""

    clean_text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
    
    patterns_to_remove = [
        r"First, I need to.*?\.", r"Okay, let's.*?[\.!]", 
        r"The user wants.*?[\.!]", r"I should start by.*?[\.!]",
        r"Based on the problem.*?[\.!]"
    ]
    for pattern in patterns_to_remove:
        clean_text = re.sub(pattern, '', clean_text, flags=re.IGNORECASE | re.DOTALL)
    
    clean_text = clean_text.replace("*", "") 

    clean_text = clean_text.strip()
    if not clean_text or len(clean_text) < 2: return

    print(f"RAYA ({lang_code}):", clean_text)
    filename = "voice.mp3"
    
    success = False
    for attempt in range(3):
        try:
            tts = gTTS(text=clean_text, lang=lang_code)
            tts.save(filename)
            success = True
            break
        except Exception as e:
            print(f"gTTS Warning on attempt {attempt+1}: {e}")
            time.sleep(1)
            
    if not success:
        print("Speak Error: Failed to connect to TTS after 3 attempts.")
        return

    try:
        time.sleep(0.4) 

        if os.name == 'nt':
            try:
                from playsound import playsound
                playsound(filename)
            except ImportError:
                import pygame
                pygame.mixer.init()
                pygame.mixer.music.load(filename)
                pygame.mixer.music.play()
                while pygame.mixer.music.get_busy():
                    pygame.time.Clock().tick(10)
                pygame.mixer.music.unload()
                pygame.mixer.quit()
        else:
            os.system(f"mpg123 -q {filename}")
        
        if os.path.exists(filename): os.remove(filename)
    except Exception as e: 
        print(f"Speak Error: {e}")

def call_api_with_thinking_sound(payload):
    sound_file = "voice_inbetween.mpeg"
    stop_event = threading.Event()
    api_result = {"data": None}
    proc = None

    def play_loop_win():
        try:
            import pygame
            pygame.mixer.init()
            if os.path.exists(sound_file):
                thinking_sound = pygame.mixer.Sound(sound_file)
                channel = thinking_sound.play(loops=-1)
                while not stop_event.is_set():
                    time.sleep(0.1)
                channel.stop()
            pygame.mixer.quit()
        except: pass

    sound_thread = None
    if os.path.exists(sound_file):
        if os.name == 'nt':
            sound_thread = threading.Thread(target=play_loop_win)
            sound_thread.start()
        else:
            try:
                proc = subprocess.Popen(["mpg123", "-q", "--loop", "-1", sound_file], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except: pass

    success = False
    for attempt in range(3):
        try:
            r = requests.post("https://api.sarvam.ai/v1/chat/completions", 
                             headers={"Authorization": f"Bearer {SARVAM_API_KEY}"}, 
                             json=payload, timeout=12)
            r.raise_for_status()
            api_result["data"] = r.json()
            success = True
            break
        except Exception as e:
            print(f"API Error attempting connection (try {attempt+1}): {e}")
            time.sleep(1)

    if sound_thread:
        stop_event.set()
        sound_thread.join()
    elif proc:
        try:
            proc.terminate()
            proc.wait()
        except: pass

    if not success or not api_result["data"] or "choices" not in api_result["data"]:
        print("CRITICAL API FAILURE: Using safe fallback response to prevent crash.")
        api_result["data"] = {
            "choices": [
                {
                    "message": {
                        "content": "Offline Fallback Mode Active.\nPlease check your internet connection.\nCould you describe more about your condition?\nIs the pain severe?\nAre you taking any medications?"
                    }
                }
            ]
        }

    return api_result["data"]

def listen_with_retry(prompt, lang_code='hi', duration=5):
    attempts = 0
    while attempts < 2:
        if prompt: speak(prompt, lang_code)
        with sr.Microphone(device_index=WORKING_MIC_INDEX) as source:
            recognizer.adjust_for_ambient_noise(source, duration=0.8)
            play_beep()
            try:
                print(">>> Listening...")
                audio = recognizer.record(source, duration=duration)
                text = recognizer.recognize_google(audio, language='hi-IN' if lang_code=='hi' else 'en-IN')
                if text.strip(): return text
            except: attempts += 1
    return ""

def main():
    print("\n--- STARTING FACE AUTHENTICATION ---\n")
    patient_name, photo_path, is_existing, face_lang = face8.run_face_recognition()
    if not patient_name:
        patient_name = "User"
        
    print(f"\n--- AUTHORIZED: {patient_name} ---\n")
    print("\n--- RAYA SMART HEALTHCARE SYSTEM ---\n")
    
    if is_existing:
        lang_choice = listen_with_retry("नमस्ते, आप हिंदी में बात करना चाहेंगे या इंग्लिश में?", "hi")
        is_hindi = "english" not in lang_choice.lower() and "इंग्लिश" not in lang_choice
        l_code, curr_lang = ('hi', 'Hindi') if is_hindi else ('en', 'English')
    else:
        l_code = face_lang if face_lang else 'hi'
        curr_lang = 'Hindi' if l_code == 'hi' else 'English'
        is_hindi = (l_code == 'hi')

    name = patient_name

    record = db.find_patient(name)
    if record:
        speak(f"स्वागत है {name}।" if is_hindi else f"Welcome back {name}.", l_code)
        patient_info = {"name": name, "age": record[1], "mobile": record[3], "photo_path": photo_path}
    else:
        speak("नए पेशेंट का पंजीकरण।" if is_hindi else "New patient registration.", l_code)
        u_age = "".join(re.findall(r'\d+', listen_with_retry("आपकी उम्र क्या है?", l_code))) or "25"
        u_mobile = "".join(re.findall(r'\d+', listen_with_retry("अपना mobile number बताएं।", l_code))) or "0000000000"
        patient_info = {"name": name, "age": u_age, "mobile": u_mobile, "photo_path": photo_path}
        db.add_patient(name, int(u_age), "Male", u_mobile)

    speak("अपनी परेशानी विस्तार से बताएं।" if is_hindi else "Describe your problem.", l_code)
    problem = listen_with_retry(None, l_code, duration=15)

    speak("मैं आपसे 5 छोटे सवाल पूछूँगी।" if is_hindi else "I will ask 5 short questions.", l_code)
    prompt_q = f"You are a doctor interviewing a patient. The patient says: '{problem}'. Ask exactly 5 follow-up medical questions directly to the patient in {curr_lang} to understand their symptoms better. Do not ask for their name or role. Provide only the 5 questions, each on a new line."
    payload_q = {"model": "sarvam-m", "messages": [{"role": "user", "content": prompt_q}]}
    q_res = call_api_with_thinking_sound(payload_q)
    
    clean_q = re.sub(r'<think>.*?</think>', '', q_res["choices"][0]["message"]["content"], flags=re.DOTALL).strip()
    questions = [l for l in clean_q.split("\n") if "?" in l]

    answers = []
    for q in questions[:5]:
        ans = listen_with_retry(q, l_code)
        answers.append(f"Q: {q}, A: {ans}")

    speak("रिपोर्ट तैयार हो रही है।" if is_hindi else "Generating report...", l_code)
    prompt_rep = f"Based on the patient's problem: '{problem}' and their answers: {answers}. Provide a concise, bulleted medical summary in strictly ENGLISH ONLY. Do NOT include any internal thoughts, explanations, or introductory text. Output ONLY the bullet points."
    payload_rep = {"model": "sarvam-m", "messages": [{"role": "user", "content": prompt_rep}]}
    final_res = call_api_with_thinking_sound(payload_rep)
    final_report = re.sub(r'<think>.*?</think>', '', final_res["choices"][0]["message"]["content"], flags=re.DOTALL).strip()

    token_details, pdf_path = processor.process_user_dynamic(patient_info, final_report, problem)

    if pdf_path: 
        if os.name == 'nt':
            open_file(pdf_path) # Retain on Windows if they prefer it there
        print_file(pdf_path)
    
    speak(f"टोकन नंबर {token_details['sub_token']}।" if is_hindi else f"Token {token_details['sub_token']}.", l_code)

if __name__ == "__main__":
    main()
