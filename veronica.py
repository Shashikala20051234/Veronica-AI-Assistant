import os
import time
import tempfile
import threading
import datetime
import webbrowser
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import urllib.parse
import subprocess
from pathlib import Path  #  added


import pyttsx3
import speech_recognition as sr
import wikipedia
import pywhatkit
import pyjokes

import pyautogui
from playsound import playsound
from gtts import gTTS

#mysql connection
import mysql.connector

# --- Database Connection (XAMPP MySQL) ---
try:
    db = mysql.connector.connect(
        host="localhost",
        user="root",         # Default XAMPP username
        password="",         # Leave blank unless you set a password
        database="veronica"   # Change this to your actual database name
    )
    cursor = db.cursor()
    print(" Connected to MySQL database successfully.")
except mysql.connector.Error as err:
    print(f" Database connection failed: {err}")
#table 
# Create a table if it doesn't exist
cursor.execute("""
CREATE TABLE IF NOT EXISTS chat_history (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_input TEXT,
    assistant_response TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
)
""")

# Function to log chat
def log_conversation(user_input, assistant_response):
    try:
        query = "INSERT INTO chat_history (user_input, assistant_response) VALUES (%s, %s)"
        cursor.execute(query, (user_input, assistant_response))
        db.commit()
    except mysql.connector.Error as err:
        print(f"⚠️ Error logging chat: {err}")
          
    # ✅ Function to speak and log both user input + response
def speak_with_log(user_input, text):
    speak(text)
    log_conversation(user_input, text)




# optional custom modules you already have
try:
    from news import news as get_news # type: ignore
except Exception:
    def get_news():
        return ["News module not found."]

try:
    from weather import temp as get_temp, des as get_weather_desc
except Exception:
    def get_temp():
        return "unknown"
    def get_weather_desc():
        return "unknown"

# ---------------- CONFIG ----------------
CONFIG = {
    "owner_name": "Friend",
    "music_dir": r"C:\Users\SANJANA\Music",
    "vscode_path": r"C:\Users\SANJANA\AppData\Local\Programs\Microsoft VS Code\Code.exe",
    "email": {
        "from_addr": "your.email@example.com",
        "smtp_server": "smtp.gmail.com",
        "smtp_port": 587,
        "username": "your.email@example.com",
        "password": "YOUR_APP_PASSWORD_OR_PASSWORD"
    }
}
# ----------------------------------------

WAKE_WORDS = ["veronica", "hey veronica"]
YOUTUBE_PROCESS = None  # to track if YouTube music is playing

# ---------------- UTILITY FUNCTIONS ----------------

def run_in_thread(fn, *a, **k):
    t = threading.Thread(target=fn, args=a, kwargs=k, daemon=True)
    t.start()
    return t

def speak(text, use_block=True):
    """Speak text using pyttsx3; fallback to gTTS+playsound if pyttsx3 fails."""
    text = str(text)
    try:
        engine = pyttsx3.init()
        voices = engine.getProperty('voices')
        if len(voices) > 1:
            try:
                engine.setProperty('voice', voices[1].id)
            except Exception:
                pass
        engine.setProperty('rate', 170)
        engine.say(text)
        engine.runAndWait()
        time.sleep(0.1)
    except Exception as e:
        try:
            tts = gTTS(text=text, lang='en')
            fd, fname = tempfile.mkstemp(suffix=".mp3")
            os.close(fd)
            tts.save(fname)
            if use_block:
                playsound(fname)
            else:
                run_in_thread(playsound, fname)
            try:
                os.remove(fname)
            except Exception:
                pass
        except Exception as e2:
            print("TTS failure:", e, e2)
            print(text)

def wishme():
    hour = datetime.datetime.now().hour
    if 0 <= hour < 12:
        speak("Good Morning!")
    elif 12 <= hour < 18:
        speak("Good Afternoon!")
    else:
        speak("Good Evening!")
    speak(f"Hello {CONFIG['owner_name']}, I am Veronica. Please tell me how may I help you?")

def takecommand(timeout=6, phrase_time_limit=8):
    """Listen from microphone and return recognized text."""
    r = sr.Recognizer()
    try:
        with sr.Microphone() as source:
            print("Listening (microphone)...")
            r.adjust_for_ambient_noise(source, duration=0.8)
            r.pause_threshold = 0.6
            try:
                audio = r.listen(source, timeout=timeout, phrase_time_limit=phrase_time_limit)
            except sr.WaitTimeoutError:
                print("Listening timed out.")
                return None
    except OSError as e:
        print("Microphone not available:", e)
        speak("Microphone not available. Please type your command.")
        try:
            typed = input("Type command: ").strip()
            return typed if typed != "" else None
        except Exception:
            return None

    try:
        query = r.recognize_google(audio, language='en-in')
        print(f"User said: {query}")
        return query
    except sr.UnknownValueError:
        print("Didn't understand audio.")
        return None
    except sr.RequestError as e:
        print("Google API error:", e)
        return None
    except Exception as e:
        print("Recognition error:", e)
        return None

def is_wake_word(text):
    if not text:
        return False
    text = text.lower()
    return any(word in text for word in WAKE_WORDS)

def send_email(to_addr, subject, body):
    cfg = CONFIG['email']
    try:
        msg = MIMEMultipart()
        msg['From'] = cfg['from_addr']
        msg['To'] = to_addr
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))
        server = smtplib.SMTP(cfg['smtp_server'], cfg['smtp_port'])
        server.ehlo()
        server.starttls()
        server.login(cfg['username'], cfg['password'])
        server.send_message(msg)
        server.quit()
        speak("Email has been sent.")
    except Exception as e:
        print("Email send error:", e)
        speak("Sorry. I was unable to send the email.")

def open_web(query):
    if not query:
        return
    q = query.strip()
    if q.startswith("http"):
        url = q
    else:
        encoded = urllib.parse.quote_plus(q)
        url = f"https://www.google.com/search?q={encoded}"
    webbrowser.open(url)
    speak("Opening web browser.")

# ---------------- APP OPENING FUNCTIONS ----------------

def open_application(query):
    """Open common Windows applications based on query text."""
    apps = {
        "word": "start winword",
        "excel": "start excel",
        "powerpoint": "start powerpnt",
        "outlook": "start outlook",
        "onenote": "start onenote",
        "notepad": "start notepad",
        "paint": "start mspaint",
        "calculator": "start calc",
        "file explorer": "start explorer",
        "settings": "start ms-settings:",
        "vscode": f'"{CONFIG["vscode_path"]}"'
    }

    for name, command in apps.items():
        if name in query:
            os.system(command)
            speak(f"Opening {name}.")
            return True
    return False

# ---------------- MUSIC CONTROL ----------------

def play_youtube_song(song):
    """Play song on YouTube and remember that process."""
    global YOUTUBE_PROCESS
    try:
        speak(f"Playing {song} on YouTube.")
        run_in_thread(pywhatkit.playonyt, song)
        YOUTUBE_PROCESS = "YOUTUBE_PLAYING"
    except Exception as e:
        print("Error playing song:", e)
        speak("Sorry, I couldn't play the song on YouTube.")

def stop_youtube_song():
    """Stop the YouTube song by closing the browser."""
    global YOUTUBE_PROCESS
    try:
        if YOUTUBE_PROCESS:
            if os.name == "nt":
                subprocess.call("taskkill /im chrome.exe /f", shell=True)
                subprocess.call("taskkill /im msedge.exe /f", shell=True)
                subprocess.call("taskkill /im firefox.exe /f", shell=True)
            else:
                os.system("pkill chrome || pkill firefox || pkill edge")
            speak("Stopped the music.")
            YOUTUBE_PROCESS = None
        else:
            speak("No music is currently playing.")
    except Exception as e:
        print("Error stopping music:", e)
        speak("Sorry, I couldn't stop the music.")

# ✅ ---------------- TAKE NOTES / DICTATION FEATURE ----------------

def take_notes():
    speak("Starting dictation mode. I am listening. Say 'stop dictation' to finish.")
    notes = []
    r = sr.Recognizer()
    filename = f"Veronica_Notes_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    file_path = Path.home() / "Desktop" / filename

    with open(file_path, "a", encoding="utf-8") as f:
        while True:
            try:
                with sr.Microphone() as source:
                    print("Listening for notes...")
                    r.adjust_for_ambient_noise(source, duration=0.5)
                    audio = r.listen(source, timeout=10, phrase_time_limit=10)

                text = r.recognize_google(audio, language="en-in").lower().strip()
                print(f"Note captured: {text}")

                if "stop dictation" in text or "stop notes" in text:
                    speak("Stopping dictation mode. Notes saved.")
                    break

                f.write(text + "\n")
                f.flush()
                notes.append(text)

            except sr.WaitTimeoutError:
                print("No speech detected, waiting...")
                continue
            except sr.UnknownValueError:
                print("Didn't catch that.")
                continue
            except Exception as e:
                print("Error during dictation:", e)
                break

    speak(f"Your notes have been saved on your desktop as {filename}.")
    os.system(f'start notepad "{file_path}"')







# ---------------- MAIN FUNCTION ----------------
def main():
    print("Starting Veronica assistant...")
    speak_with_log("startup", "Hello " + CONFIG['owner_name'] + ". This is Veronica.")
    wishme()

    while True:
        raw = takecommand()
        if raw is None:
            time.sleep(0.3)
            continue

        query = raw.lower().strip()
        print("Received query:", query)

        if not is_wake_word(query):
            print("Wake word not detected.")
            continue

        for w in WAKE_WORDS:
            query = query.replace(w, '').strip()

        if query == "":
            speak_with_log(query, "Yes?")
            continue

        try:
            if 'take notes' in query or 'start dictation' in query:
                take_notes()
                continue

            if 'open' in query:
                if open_application(query):
                    continue

            if any(x in query for x in ['wikipedia', 'who is', 'what is', 'tell me about', 'search']):
                clean = query
                for w in ['wikipedia', 'who is', 'what is', 'tell me about', 'search']:
                    clean = clean.replace(w, '')
                clean = clean.strip()
                if clean == "":
                    speak_with_log(query, "Please tell me what to search on Wikipedia.")
                    continue
                speak_with_log(query, "Searching Wikipedia...")
                try:
                    results = wikipedia.summary(clean, sentences=2)
                    print("WIKI:", results)
                    speak_with_log(query, results)
                except Exception as e:
                    print("Wikipedia error:", e)
                    speak_with_log(query, "Sorry, I couldn't find that on Wikipedia.")

            elif query.startswith('open ') or query.startswith('find '):
                item = query.replace('open', '').replace('find', '').strip()
                open_web(item)

            elif 'who are you' in query or 'what can you do' in query:
                speak_with_log(query, "I am Veronica, your personal assistant. I can search Wikipedia, open applications, play YouTube, tell jokes, show news and weather, check speed, operate your camera, and more.")

            elif query in ['hi', 'hello']:
                speak_with_log(query, f"Hello {CONFIG['owner_name']}")

            elif 'play music' in query or 'play song' in query:
                try:
                    music_dir = CONFIG['music_dir']
                    songs = os.listdir(music_dir)
                    if songs:
                        first = os.path.join(music_dir, songs[0])
                        os.startfile(first)
                        speak_with_log(query, "Playing music from your folder.")
                    else:
                        speak_with_log(query, "No music found in your folder.")
                except Exception as e:
                    print("Play music error:", e)
                    speak_with_log(query, "Couldn't play music. Check your music folder path.")

            elif query.startswith('play '):
                song = query.replace('play', '').replace('on youtube', '').strip()
                if song:
                    play_youtube_song(song)
                else:
                    speak_with_log(query, "What should I play?")

            elif 'stop music' in query or 'pause music' in query or 'stop the song' in query:
                stop_youtube_song()

            elif 'the time' in query or 'what time' in query:
                t = datetime.datetime.now().strftime("%I:%M:%S %p")
                speak_with_log(query, f"The time is {t}")

            elif 'joke' in query:
                j = pyjokes.get_joke()
                speak_with_log(query, j)

            elif 'news' in query:
                headlines = get_news()
                for i, h in enumerate(headlines[:5]):
                    speak_with_log(query, f"News {i+1}: {h}")

            elif 'weather' in query:
                temperatur = get_temp()
                description = get_weather_desc()
                speak_with_log(query, f"The temperature in Belgaum is {temperatur} degree Celsius.")
                speak_with_log(query, f"The weather is {description}.")

            elif 'camera' in query or 'open camera' in query:
                try:
                    speak_with_log(query, "Opening system camera app.")
                    subprocess.run('start "" microsoft.windows.camera:', shell=True)
                except Exception as e:
                    print("Error opening system camera:", e)
                    speak_with_log(query, "Sorry, I couldn't open the system camera.")

            elif 'increase' in query and 'volume' in query:
                for _ in range(5):
                    pyautogui.press("volumeup")
                    time.sleep(0.05)
                speak_with_log(query, "Increased volume.")

            elif 'decrease' in query and 'volume' in query:
                for _ in range(5):
                    pyautogui.press("volumedown")
                    time.sleep(0.05)
                speak_with_log(query, "Decreased volume.")

            elif 'mute' in query and 'volume' in query:
                pyautogui.press("volumemute")
                speak_with_log(query, "Muted volume.")

            elif 'unmute' in query:
                pyautogui.press("volumemute")
                speak_with_log(query, "Unmuted volume.")

            elif 'increase' in query and 'brightness' in query:
                try:
                    import screen_brightness_control as sbc
                    current = sbc.get_brightness(display=0)[0]
                    new_value = min(current + 10, 100)
                    sbc.set_brightness(new_value)
                    speak_with_log(query, f"Brightness increased by ten percent.")
                except Exception as e:
                    print("Brightness increase error:", e)
                    speak_with_log(query, "Sorry, I couldn't increase the brightness.")

            elif 'decrease' in query and 'brightness' in query:
                try:
                    import screen_brightness_control as sbc
                    current = sbc.get_brightness(display=0)[0]
                    new_value = max(current - 10, 0)
                    sbc.set_brightness(new_value)
                    speak_with_log(query, f"Brightness decreased by 10 percent.")
                except Exception as e:
                    print("Brightness decrease error:", e)
                    speak_with_log(query, "Sorry, I couldn't decrease the brightness.")

            elif 'set brightness' in query:
                try:
                    import screen_brightness_control as sbc
                    import re
                    match = re.search(r'(\d+)', query)
                    if match:
                        val = int(match.group(1))
                        sbc.set_brightness(val)
                        speak_with_log(query, f"Brightness set to {val} percent.")
                    else:
                        speak_with_log(query, "Please tell me the brightness level in percentage.")
                except Exception as e:
                    print("Brightness set error:", e)
                    speak_with_log(query, "Sorry, I couldn't change the brightness.")

            elif 'brightness' in query and ('what' in query or 'current' in query):
                try:
                    import screen_brightness_control as sbc
                    current = sbc.get_brightness(display=0)[0]
                    speak_with_log(query, f"The current brightness is {current} percent.")
                except Exception as e:
                    print("Brightness read error:", e)
                    speak_with_log(query, "Sorry, I couldn't read the brightness level.")

            elif 'screenshot' in query or 'take screenshot' in query:
                try:
                    desktop = Path.home() / "Desktop"
                    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"screenshot_{timestamp}.png"
                    file_path = desktop / filename
                    image = pyautogui.screenshot()
                    image.save(file_path)
                    speak_with_log(query, f"Screenshot taken and saved on your desktop.")
                    print(f"Screenshot saved at: {file_path}")
                except Exception as e:
                    print("Screenshot error:", e)
                    speak_with_log(query, "Sorry, I couldn't take a screenshot.")

            elif 'create' in query and ('file' in query or 'document' in query or 'presentation' in query or 'sheet' in query):
                try:
                    desktop = Path.home() / "Desktop"
                    speak_with_log(query, "What should be the name of the file?")
                    name_raw = takecommand()
                    if not name_raw:
                        speak_with_log(query, "File creation cancelled.")
                        continue
                    name = name_raw.replace(" ", "_").strip()
                    if name == "":
                        name = "Untitled"

                    if 'word' in query or 'document' in query:
                        file_path = desktop / f"{name}.docx"
                        open(file_path, 'w').close()
                        speak_with_log(query, f"Creating a new Word document named {name} on your desktop.")
                        os.system(f'start winword "{file_path}"')

                    elif 'powerpoint' in query or 'presentation' in query:
                        file_path = desktop / f"{name}.pptx"
                        open(file_path, 'w').close()
                        speak_with_log(query, f"Creating a new PowerPoint presentation named {name} on your desktop.")
                        os.system(f'start powerpnt "{file_path}"')

                    elif 'excel' in query or 'sheet' in query:
                        file_path = desktop / f"{name}.xlsx"
                        open(file_path, 'w').close()
                        speak_with_log(query, f"Creating a new Excel sheet named {name} on your desktop.")
                        os.system(f'start excel "{file_path}"')
                    else:
                        speak_with_log(query, "Please specify whether you want Word, PowerPoint, or Excel file.")
                except Exception as e:
                    print("File creation error:", e)
                    speak_with_log(query, "Sorry, I couldn't create the file right now.")

            elif 'calculate' in query or 'plus' in query or 'minus' in query or 'multiply' in query or 'divide' in query:
                try:
                    expr = query
                    expr = expr.replace('calculate', '').replace('what is', '')
                    expr = expr.replace('plus', '+').replace('minus', '-')
                    expr = expr.replace('multiply', '').replace('multiplied by', '')
                    expr = expr.replace('into', '*').replace('divide', '/').replace('divided by', '/')
                    expr = expr.replace('x', '*')
                    expr = expr.strip()
                    result = eval(expr, {"_builtins_": {}})
                    speak_with_log(query, f"The answer is {result}")
                    print(f"Calculation: {expr} = {result}")
                except Exception as e:
                    print("Calculation error:", e)
                    speak_with_log(query, "Sorry, I could not calculate that.")

            elif 'exit' in query or 'quit' in query or 'bye' in query:
                speak_with_log(query, "Bye " + CONFIG['owner_name'] + ". Have a nice day.")
                break

            else:
                speak_with_log(query, "I will search that on the web.")
                open_web(query)

        except Exception as e:
            print("Error handling command:", e)
            speak_with_log(query, "Sorry, I encountered an error while handling that command.")




# ---------------- ENTRYPOINT ----------------
if __name__ == "__main__":
    main()
