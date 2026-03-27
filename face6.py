import cv2
import face_recognition
import sqlite3
import pickle
import numpy as np
import time
import speech_recognition as sr
from gtts import gTTS
import os
import threading
import argparse
import sys

try:
    from playsound import playsound
    HAS_PLAYSOUND = True
except ImportError:
    HAS_PLAYSOUND = False

# -------------------------------
# Configuration
# -------------------------------
SCALE_FACTOR = 0.25
RECOGNITION_THRESHOLD = 0.5
FRAME_SKIP = 4
FACES_DIR = "user_faces"
os.makedirs(FACES_DIR, exist_ok=True)

# -------------------------------
# Database Setup
# -------------------------------
conn = sqlite3.connect("faces5.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute(""" 
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY, 
        name TEXT, 
        encoding BLOB,
        photo_path TEXT DEFAULT NULL
    ) 
""")
cursor.execute(""" CREATE TABLE IF NOT EXISTS logs( name TEXT, time TEXT ) """)
conn.commit()

known_names = []
known_encodings = []

def reload_faces():
    global known_names, known_encodings
    cursor.execute("SELECT name, encoding FROM users")
    known_names = []
    known_encodings = []
    for row in cursor.fetchall():
        known_names.append(row[0])
        if row[1]:
            known_encodings.append(pickle.loads(row[1]))

reload_faces()

# -------------------------------
# Global State
# -------------------------------
LANG = 'en'
session_active = False
program_running = True

display_text1 = ""
display_text2 = ""
countdown_number = 0
photo_to_confirm = None

def speak(text, lang_code=None):
    if lang_code is None:
        lang_code = LANG
    print(f"[AI Speak]: {text}")
    try:
        tts = gTTS(text=text, lang=lang_code, slow=False)
        filename = "temp_speech.mp3"
        tts.save(filename)
        
        if os.name == "nt" and HAS_PLAYSOUND:
            playsound(filename)
        else:
            os.system(f"mpg123 -q {filename}")
            
        if os.path.exists(filename):
            os.remove(filename)
    except Exception as e:
        print("Speech error:", e)

def listen(timeout_sec=8, phrase_time=5, lang_code=None):
    if lang_code is None:
        lang_code = LANG
    
    recognizer = sr.Recognizer()
    recognizer.energy_threshold = 150
    recognizer.dynamic_energy_threshold = True

    try:
        with sr.Microphone() as source:
            # 200ms stabilization block to let the Windows hardware mic fully open 
            # before we begin strictly passing frames to Google STT. 
            # This perfectly prevents the first letter of 'yes' from getting hardware-clipped!
            recognizer.adjust_for_ambient_noise(source, duration=0.2)
            print("[Listening...]")
            
            audio = recognizer.listen(source, timeout=timeout_sec, phrase_time_limit=phrase_time)
            text = recognizer.recognize_google(audio, language=lang_code)
            print(f"[Heard]: {text}")
            return text.lower().strip()
    except sr.WaitTimeoutError:
        print("[Silence timeout]")
        return ""
    except sr.UnknownValueError:
        print("[Could not understand audio]")
        return ""
    except Exception as e:
        print("[Listen error]:", e)
        return ""

yes_words = ['yes', 'yep', 'yeah', 'haan', 'ha', 'ji', 'jee', 'ok', 'right', 'correct', 'y', 'theek', 'हां', 'जी', 'ठीक']
no_words = ['no', 'nope', 'nah', 'nahi', 'na', 'wrong', 'incorrect', 'n', 'galat', 'नहीं', 'ना']

def is_affirmative(text):
    return any(w in text.split() for w in yes_words)

def is_negative(text):
    return any(w in text.split() for w in no_words)

def interaction_flow(target_encoding):
    global session_active, LANG, display_text1, display_text2, countdown_number, photo_to_confirm, program_running

    try:
        display_text1 = "Language Selection"
        display_text2 = "Speak 'English' or 'Hindi'"
        
        speak("Which language do you prefer? Say English, or Hindi.", lang_code='en')
        lang_response = listen(lang_code='en-IN')
        
        if 'hindi' in lang_response:
            LANG = 'hi'
            speak("Maine Hindi set kar di hai.", lang_code='hi')
        else:
            LANG = 'en'
            speak("I have set the language to English.", lang_code='en')

        clean_name = ""
        while True:
            display_text1 = "Listening..."
            display_text2 = "Please say your name"
            if LANG == 'hi':
                speak("Kripya apna pura naam bataye.", lang_code='hi')
            else:
                speak("Please say your full name.", lang_code='en')
            
            name_resp = listen(lang_code='en-IN') 
            if not name_resp:
                if LANG == 'hi': speak("Main samajh nahi payi. Phir se koshish karein.", lang_code='hi')
                else: speak("I didn't catch that. Please try again.", lang_code='en')
                continue
            
            prefixes = ["my name is ", "i am ", "this is ", "mera naam ", "naam ", "hai "]
            clean_name = name_resp
            for p in prefixes:
                if clean_name.startswith(p):
                    clean_name = clean_name[len(p):].strip()
            
            clean_name = clean_name.title()
            if len(clean_name) < 2:
                continue

            display_text1 = f"Name: {clean_name}"
            display_text2 = "Did I hear perfectly?"

            if LANG == 'hi':
                speak(f"Kya aapka naam {clean_name} hai? Haan, ya nahi?", lang_code='hi')
            else:
                speak(f"Did I hear correctly? Is your name {clean_name}? Yes, or no?", lang_code='en')
            
            conf_resp = listen(lang_code='en-IN' if LANG=='en' else 'hi-IN')
            if is_affirmative(conf_resp):
                break
            else:
                if LANG == 'hi': speak("Theek hai, chaliye wapas shuru karte hain.", lang_code='hi')
                else: speak("Alright, let's try again.", lang_code='en')

        # 3. Photo Capture
        while True:
            display_text1 = "Get Ready for Photo"
            display_text2 = "Look straight at the camera!"
            if LANG == 'hi':
                speak("Ab main aapki photo lungi. Kripya camera ki taraf dekhein, aur khade rahein.", lang_code='hi')
            else:
                speak("I will now capture your photo. Please look straight at the camera.", lang_code='en')

            display_text1 = "Taking photo in..."
            for i in range(3, 0, -1):
                countdown_number = i
                speak(str(i), lang_code='en-IN')
                time.sleep(0.3)
                
            countdown_number = 0
            display_text1 = "SNAP!"
            speak("Snap!" if LANG=='en' else "Kheench li!", lang_code='en' if LANG=='en' else 'hi')
            
            photo_to_confirm = True 
            while photo_to_confirm is True:
                time.sleep(0.1) 
                
            captured_crop = photo_to_confirm
            
            # Ask if ok
            if LANG == 'hi':
                speak("Kya yeh image theek hai? Haan, ya nahi?", lang_code='hi')
            else:
                speak("Is this image okay? Yes, or no?", lang_code='en')

            photo_resp = listen(lang_code='en-IN' if LANG=='en' else 'hi-IN')
            
            if is_affirmative(photo_resp):
                filename = os.path.join(FACES_DIR, clean_name.replace(" ", "_").lower() + f"_{int(time.time())}.jpg")
                cv2.imwrite(filename, captured_crop)
                
                blob = pickle.dumps(target_encoding)
                cursor.execute("INSERT INTO users (name, encoding, photo_path) VALUES (?,?,?)",
                               (clean_name, blob, filename))
                conn.commit()
                reload_faces()

                display_text1 = "Success!"
                display_text2 = ""
                # GREET WITH NAMASTE NO MATTER WHAT, THEN EXIT
                speak(f"Namaste {clean_name}", lang_code=LANG)
                time.sleep(0.5)
                program_running = False # END
                break
            else:
                if LANG == 'hi': speak("Theek hai, ek aur photo lete hain.", lang_code='hi')
                else: speak("Alright, let's take another one.", lang_code='en')
                photo_to_confirm = None

    finally:
        session_active = False
        display_text1 = ""
        display_text2 = ""
        photo_to_confirm = None

def greet_known_user(name):
    global program_running
    speak(f"Namaste {name}", lang_code=LANG)
    time.sleep(0.5)
    program_running = False

def manual_register(img_path, name):
    if not os.path.exists(img_path):
        print(f"ERROR: Image not found at {img_path}")
        sys.exit(1)

    print(f"Loading and vectorizing image for {name}...")
    # Load using face_recognition (reads in RGB)
    image = face_recognition.load_image_file(img_path)
    encodings = face_recognition.face_encodings(image)

    if len(encodings) == 0:
        print("ERROR: No face detected in the provided image.")
        sys.exit(1)
    elif len(encodings) > 1:
        print("WARNING: Multiple faces detected. Using the primary prominent face.")

    target_encoding = encodings[0]
    
    # Convert RGB back to BGR for OpenCV saving
    bgr_image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
    
    h, w, _ = bgr_image.shape
    if min(h, w) > 0:
        # Resize proportionally to fit perfectly inside MongoDB-ready 600x600 size
        scale = min(600/w, 600/h)
        if scale < 1.0:
            bgr_image = cv2.resize(bgr_image, (int(w*scale), int(h*scale)))
    
    clean_name = name.title().strip()
    filename = os.path.join(FACES_DIR, clean_name.replace(" ", "_").lower() + f"_{int(time.time())}.jpg")
    cv2.imwrite(filename, bgr_image)
    
    # Inject directly into SQL DB
    blob = pickle.dumps(target_encoding)
    cursor.execute("INSERT INTO users (name, encoding, photo_path) VALUES (?,?,?)",
                   (clean_name, blob, filename))
    conn.commit()
    
    print(f"✅ SUCCESS: Formally vectorized and registered {clean_name} directly into the database!")
    print(f"✅ Image cleanly formatted and securely saved to: {filename}")

def main():
    global session_active, photo_to_confirm, program_running
    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    cap.set(3, 1280)
    cap.set(4, 720)

    frame_count = 0

    print("====================================")
    print("RAYA Vision 6 - Final Implementation")
    print("====================================")

    while program_running:
        ret, frame = cap.read()
        if not ret:
            break
            
        frame = cv2.flip(frame, 1)
        h, w, _ = frame.shape
        clean_frame = frame.copy() # KEEP A CLEAN COPY FOR PHOTO CAPTURE
        
        frame_count += 1

        if session_active:
            overlay = frame.copy()
            cv2.rectangle(overlay, (0, 0), (w, h), (0, 0, 0), -1)
            cv2.addWeighted(overlay, 0.4, frame, 0.6, 0, frame)

            if countdown_number > 0:
                cv2.putText(frame, str(countdown_number), (w//2 - 50, h//2 + 50),
                            cv2.FONT_HERSHEY_SIMPLEX, 5, (0, 255, 255), 10)
            
            if display_text1:
                cv2.putText(frame, display_text1, (30, 60), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            if display_text2:
                cv2.putText(frame, display_text2, (30, 110), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)

            if photo_to_confirm is True:
                # CROP FROM CLEAN FRAME
                cx, cy = w//2, h//2
                sz = 300
                y1 = max(0, cy-sz)
                y2 = min(h, cy+sz)
                x1 = max(0, cx-sz)
                x2 = min(w, cx+sz)
                cropped = clean_frame[y1:y2, x1:x2].copy()
                
                if cropped.shape[0] > 0 and cropped.shape[1] > 0:
                    cropped = cv2.resize(cropped, (600, 600))
                    photo_to_confirm = cropped

            elif isinstance(photo_to_confirm, np.ndarray):
                ph, pw, _ = photo_to_confirm.shape
                start_x = w//2 - pw//2
                start_y = h//2 - ph//2
                
                if start_x >= 0 and start_y >= 0:
                    frame[start_y:start_y+ph, start_x:start_x+pw] = photo_to_confirm
                    cv2.rectangle(frame, (start_x, start_y), (start_x+pw, start_y+ph), (255, 255, 0), 4)

        else:
            if frame_count % FRAME_SKIP == 0:
                small = cv2.resize(clean_frame, (0, 0), fx=SCALE_FACTOR, fy=SCALE_FACTOR)
                rgb = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
                locations = face_recognition.face_locations(rgb, model="hog")
                
                if locations:
                    encodings = face_recognition.face_encodings(rgb, locations)

                    for (top, right, bottom, left), encoding in zip(locations, encodings):
                        name = "Unknown"
                        if len(known_encodings) > 0:
                            distances = face_recognition.face_distance(known_encodings, encoding)
                            best_idx = np.argmin(distances)
                            if distances[best_idx] < RECOGNITION_THRESHOLD:
                                name = known_names[best_idx]
                        
                        top = int(top / SCALE_FACTOR)
                        right = int(right / SCALE_FACTOR)
                        bottom = int(bottom / SCALE_FACTOR)
                        left = int(left / SCALE_FACTOR)

                        color = (0, 255, 0) if name != "Unknown" else (0, 0, 255)
                        cv2.rectangle(frame, (left, top), (right, bottom), color, 2)
                        cv2.putText(frame, name, (left, top-10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)

                        if name != "Unknown":
                            session_active = True
                            threading.Thread(target=greet_known_user, args=(name,), daemon=True).start()
                            break 
                        else:
                            session_active = True
                            threading.Thread(target=interaction_flow, args=(encoding,), daemon=True).start()
                            break

        cv2.imshow("RAYA - Vision 6", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()
    print("Program gracefully exited. Moving to next module...")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="RAYA Vision 6 System")
    parser.add_argument("--register", type=str, help="Path to a photo for manual offline registration")
    parser.add_argument("--name", type=str, help="Name of the person being registered")
    
    args, unknown = parser.parse_known_args()

    if args.register:
        if not args.name:
            print("ERROR: You must provide a name using --name when registering a photo manually.")
            print('Example usage: python face6.py --register "photo.jpg" --name "Aditya Singh"')
            sys.exit(1)
        else:
            manual_register(args.register, args.name)
    else:
        main()
