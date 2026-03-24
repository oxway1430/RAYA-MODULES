import cv2
import face_recognition
import sqlite3
import pickle
import numpy as np
from datetime import datetime
import time
import speech_recognition as sr
from gtts import gTTS
from playsound import playsound
import os

# -------------------------------
# Performance Settings
# -------------------------------
SCALE_FACTOR = 0.25
RECOGNITION_THRESHOLD = 0.5
COOLDOWN_SECONDS = 8
FRAME_SKIP = 4

# -------------------------------
# BLOCKING SPEECH ENGINE using gTTS (Hindi support ONLY for Namaste)
# -------------------------------
def speak(text, wait_after=1.8, lang='en'):
    print("RAYA:", text)
    try:
        filename = "temp_speech.mp3"
        tts = gTTS(text=text, lang=lang, slow=False)
        tts.save(filename)
        playsound(filename)
        os.remove(filename)
        time.sleep(wait_after)
    except Exception as e:
        print("Speech error:", e)

# -------------------------------
# Simple Speech Recognition (No confirmation)
# -------------------------------
def listen_for_name(max_attempts=3):
    recognizer = sr.Recognizer()
    recognizer.energy_threshold = 400
    recognizer.dynamic_energy_threshold = False
    for attempt in range(max_attempts):
        if attempt == 0:
            speak("New face detected. Please say your full name clearly.", 2.2)
        else:
            speak("Please say your name again clearly.", 1.8)
        with sr.Microphone() as source:
            try:
                recognizer.adjust_for_ambient_noise(source, duration=0.8)
                audio = recognizer.listen(source, timeout=8, phrase_time_limit=6)
                name_text = recognizer.recognize_google(audio)
                name = name_text.strip().title()
                prefixes = ["my name is ", "i am ", "this is ", "name is ", "hi my name is ", "its ", "it's ", "hello i am ", "my name ", "name "]
                for prefix in prefixes:
                    if name.lower().startswith(prefix):
                        name = name[len(prefix):].strip().title()
                if name and len(name) > 1:
                    speak(f"Registering you as {name}", 1.5)
                    return name
            except sr.UnknownValueError:
                speak("Sorry, I couldn't understand what you said.", 1.3)
            except Exception:
                speak("Sorry, there was an error listening.", 1.3)
    speak("I couldn't understand your name after multiple attempts. Registration cancelled.", 1.5)
    return None

# -------------------------------
# Database
# -------------------------------
conn = sqlite3.connect("faces.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute(""" CREATE TABLE IF NOT EXISTS users( id INTEGER PRIMARY KEY, name TEXT, encoding BLOB ) """)
cursor.execute(""" CREATE TABLE IF NOT EXISTS logs( name TEXT, time TEXT ) """)
conn.commit()

# -------------------------------
# Load Known Faces
# -------------------------------
known_names = []
known_encodings = []

def reload_faces():
    global known_names, known_encodings
    cursor.execute("SELECT name,encoding FROM users")
    known_names = []
    known_encodings = []
    for row in cursor.fetchall():
        known_names.append(row[0])
        known_encodings.append(pickle.loads(row[1]))

reload_faces()

# -------------------------------
# Add User
# -------------------------------
def add_user(name, encoding):
    blob = pickle.dumps(encoding)
    cursor.execute("INSERT INTO users VALUES (NULL,?,?)", (name, blob))
    conn.commit()
    reload_faces()
    speak(f"{name} has been registered successfully", 1.0)

# -------------------------------
# Log Access
# -------------------------------
def log_access(name):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("INSERT INTO logs VALUES (?,?)", (name, now))
    conn.commit()

# -------------------------------
# Recognition
# -------------------------------
def recognize(face_encoding):
    if len(known_encodings) == 0:
        return "Unknown", 0
    distances = face_recognition.face_distance(known_encodings, face_encoding)
    best_idx = np.argmin(distances)
    best_distance = distances[best_idx]
    confidence = (1 - min(best_distance, 1)) * 100
    if best_distance < RECOGNITION_THRESHOLD:
        return known_names[best_idx], confidence
    return "Unknown", confidence

# -------------------------------
# Cooldowns
# -------------------------------
last_greeted = {}
last_registration_prompt = 0

def should_greet(name):
    now = time.time()
    if name not in last_greeted:
        return True
    return (now - last_greeted[name]) > COOLDOWN_SECONDS

def update_greeted(name):
    last_greeted[name] = time.time()

def should_prompt_registration():
    global last_registration_prompt
    now = time.time()
    return (now - last_registration_prompt) > 12

def update_registration_prompt():
    global last_registration_prompt
    last_registration_prompt = time.time()

# -------------------------------
# Main Program
# -------------------------------
def main():
    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    cap.set(3, 320)
    cap.set(4, 240)
    if not cap.isOpened():
        print("ERROR: Camera could not be opened!")
        print("→ Close all other apps using camera (Zoom, Teams, Chrome, etc.)")
        print("→ Windows Settings → Privacy → Camera → Turn ON access")
        return None

    frame_count = 0
    speak("AI security system started. Camera is now active.", 1.5)

    while True:
        ret, frame = cap.read()
        if not ret:
            speak("Camera disconnected.", 1.0)
            break

        frame = cv2.flip(frame, 1)
        frame_count += 1
        if frame_count % FRAME_SKIP != 0:
            cv2.imshow("RAYA AI Security", frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
            continue

        small = cv2.resize(frame, (0,0), fx=SCALE_FACTOR, fy=SCALE_FACTOR)
        rgb = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
        locations = face_recognition.face_locations(rgb, model="hog")
        encodings = face_recognition.face_encodings(rgb, locations)

        for (top, right, bottom, left), encoding in zip(locations, encodings):
            top = int(top / SCALE_FACTOR)
            right = int(right / SCALE_FACTOR)
            bottom = int(bottom / SCALE_FACTOR)
            left = int(left / SCALE_FACTOR)

            name, confidence = recognize(encoding)

            color = (0, 255, 0) if name != "Unknown" else (0, 0, 255)
            cv2.rectangle(frame, (left, top), (right, bottom), color, 2)
            cv2.putText(frame, f"{name} {confidence:.1f}%", (left, top-10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

            if name != "Unknown":
                if should_greet(name):
                    speak(f"Namaste {name}", 0.5, lang='hi')          # Hindi only here
                    log_access(name)
                    update_greeted(name)
                    
                    # === AFTER SUCCESSFUL RECOGNITION: CLOSE CAMERA AND EXIT TO NEXT MODULE ===
                    print(f"\n✅ Face recognized: {name}")
                    print("   Closing security system and moving to next module...\n")
                    cap.release()
                    cv2.destroyAllWindows()
                    return name

            else:
                if should_prompt_registration():
                    registered_name = listen_for_name()
                    if registered_name:
                        add_user(registered_name, encoding)
                        speak(f"Namaste {registered_name}", 1.0, lang='hi')  # Hindi only here
                        log_access(registered_name)
                        update_greeted(registered_name)
                        update_registration_prompt()
                        
                        # === AFTER SUCCESSFUL REGISTRATION: CLOSE CAMERA AND EXIT TO NEXT MODULE ===
                        print(f"\n✅ New user registered: {registered_name}")
                        print("   Closing security system and moving to next module...\n")
                        cap.release()
                        cv2.destroyAllWindows()
                        return registered_name

        cv2.putText(frame, "Press q to quit", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        cv2.imshow("RAYA AI Security", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
        time.sleep(0.01)

    cap.release()
    cv2.destroyAllWindows()
    return None

if __name__ == "__main__":
    recognized_person = main()
    if recognized_person:
        print(f"Welcome back, {recognized_person}! Proceeding to next module...")
        # ========================
        # ←←← PUT YOUR NEXT MODULE CODE RIGHT HERE ←←←
        # Example: next_module(recognized_person)
        # ========================
    else:
        print("Program ended without recognition.")