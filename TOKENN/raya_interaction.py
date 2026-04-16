
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
import face7

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
                subprocess.run(['lp', os.path.abspath(path)], check=True)
    except ImportError:
        print("To print to a specific printer on Windows, please open terminal and run: pip install pywin32")
    except Exception as e:
        print(f"Print Error: {e}")

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
    try:
        tts = gTTS(text=clean_text, lang=lang_code)
        tts.save(filename)
        
        time.sleep(0.4) 

        pygame.mixer.init()
        pygame.mixer.music.load(filename)
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            pygame.time.Clock().tick(10)
        pygame.mixer.music.unload()
        pygame.mixer.quit()
        
        if os.path.exists(filename): os.remove(filename)
    except Exception as e: 
        print(f"Speak Error: {e}")

def call_api_with_thinking_sound(payload):
    sound_file = "voice_inbetween.mpeg"
    stop_event = threading.Event()
    api_result = {"data": None}

    def play_loop():
        pygame.mixer.init()
        if os.path.exists(sound_file):
            try:
                thinking_sound = pygame.mixer.Sound(sound_file)
                channel = thinking_sound.play(loops=-1)
                while not stop_event.is_set():
                    time.sleep(0.1)
                channel.stop()
            except: pass
        pygame.mixer.quit()

    sound_thread = threading.Thread(target=play_loop)
    sound_thread.start()

    try:
        r = requests.post("https://api.sarvam.ai/v1/chat/completions", 
                         headers={"Authorization": f"Bearer {SARVAM_API_KEY}"}, 
                         json=payload)
        api_result["data"] = r.json()
    except Exception as e:
        print(f"API Error: {e}")

    stop_event.set()
    sound_thread.join()
    return api_result["data"]

def listen_with_retry(prompt, lang_code='hi', duration=5):
    attempts = 0
    while attempts < 2:
        if prompt: speak(prompt, lang_code)
        with sr.Microphone() as source:
            recognizer.adjust_for_ambient_noise(source, duration=0.8)
            try:
                print(">>> Listening...")
                audio = recognizer.record(source, duration=duration)
                text = recognizer.recognize_google(audio, language='hi-IN' if lang_code=='hi' else 'en-IN')
                if text.strip(): return text
            except: attempts += 1
    return ""

def main():
    print("\n--- STARTING FACE AUTHENTICATION ---\n")
    patient_name, photo_path = face7.run_face_recognition()
    if not patient_name:
        patient_name = "User"
        
    print(f"\n--- AUTHORIZED: {patient_name} ---\n")
    print("\n--- RAYA SMART HEALTHCARE SYSTEM ---\n")
    
    lang_choice = listen_with_retry("नमस्ते, आप हिंदी में बात करना चाहेंगे या इंग्लिश में?", "hi")
    is_hindi = "english" not in lang_choice.lower() and "इंग्लिश" not in lang_choice
    l_code, curr_lang = ('hi', 'Hindi') if is_hindi else ('en', 'English')

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
        open_file(pdf_path)
        print_file(pdf_path)
    
    speak(f"टोकन नंबर {token_details['sub_token']}।" if is_hindi else f"Token {token_details['sub_token']}.", l_code)

if __name__ == "__main__":
    main()
