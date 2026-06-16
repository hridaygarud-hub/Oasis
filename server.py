

import random as rd
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, Response
import os
import google.generativeai as genai_v1
from google import genai as genai_v2
from google.genai import types
from elevenlabs import ElevenLabs
from dotenv import load_dotenv
import tempfile
import time
import sqlite3

load_dotenv()

genai_client_v2 = genai_v2.Client(api_key=os.getenv("GEMINI_API_KEY"), http_options={'api_version': 'v1beta'})
genai_v1.configure(api_key=os.getenv("GEMINI_API_KEY"))
eleven_client = ElevenLabs(api_key=os.getenv("ELEVENLABS_API_KEY"))
import csv
import pandas as pd
from datetime import datetime, timedelta

from chat import get_oasis_response, chat_with_gemini
from vector_engine import (
    compute_user_vector,
    incremental_update,
    get_all_user_ids,
)
from recommendation_engine import (
    get_recommendations,
    apply_feedback,
    apply_activity_effect,
    ACTIVITIES,
)
import os
import json
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

b = 0
app = Flask(__name__, template_folder='.', static_folder='.', static_url_path='')
app.secret_key = "supersecretkey"

FILE = "user_behaviour.csv"
DB_FILE = "oasis_game.db"
CLIENT_SECRETS_FILE = "credentials.json"
REDIRECT_URI = "http://localhost:5035/oauth2callback"
SCOPES = [
    'https://www.googleapis.com/auth/calendar.events',
    'https://www.googleapis.com/auth/fitness.heart_rate.read',
    'https://www.googleapis.com/auth/fitness.sleep.read'
]
HEADERS = ["user_id", "event_type", "item_id", "duration", "timestamp", "emotion"]

DEFAULT_MISSIONS = {
    "breathing": {
        "title": "Breathing Grove",
        "description": "Complete a 60-second breathing reset.",
        "points": 40,
        "emotion": "calm",
    },
    "gratitude": {
        "title": "Gratitude Spring",
        "description": "Name one thing that went okay today.",
        "points": 35,
        "emotion": "joy",
    },
    "grounding": {
        "title": "Grounding Stones",
        "description": "Notice five things around you.",
        "points": 35,
        "emotion": "neutral",
    },
    "planner": {
        "title": "Tiny Plan Bridge",
        "description": "Choose one small next step.",
        "points": 45,
        "emotion": "focused",
    },
}

def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_game_db():
    with get_db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                display_name TEXT NOT NULL,
                avatar_color TEXT NOT NULL,
                skin TEXT NOT NULL,
                points INTEGER NOT NULL DEFAULT 0,
                xp INTEGER NOT NULL DEFAULT 0,
                level INTEGER NOT NULL DEFAULT 1,
                streak INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS progress_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                mission_id TEXT NOT NULL,
                mission_title TEXT NOT NULL,
                points INTEGER NOT NULL,
                mood TEXT,
                note TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS presence (
                user_id TEXT PRIMARY KEY,
                display_name TEXT NOT NULL,
                avatar_color TEXT NOT NULL,
                skin TEXT NOT NULL,
                x REAL NOT NULL DEFAULT 0,
                y REAL NOT NULL DEFAULT 0,
                z REAL NOT NULL DEFAULT 0,
                level INTEGER NOT NULL DEFAULT 1,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS chat_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sender_id TEXT NOT NULL,
                message TEXT NOT NULL,
                x REAL NOT NULL,
                y REAL NOT NULL,
                z REAL NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )

def upsert_game_user(user_id, display_name="Explorer", avatar_color="#8b5cf6", skin="oasis"):
    now = datetime.now().isoformat()
    with get_db() as conn:
        existing = conn.execute(
            "SELECT * FROM users WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        if existing:
            conn.execute(
                "UPDATE users SET display_name = ?, avatar_color = ?, skin = ?, updated_at = ? WHERE user_id = ?",
                (display_name, avatar_color, skin, now, user_id),
            )
        else:
            conn.execute(
                "INSERT INTO users (user_id, display_name, avatar_color, skin, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                (user_id, display_name, avatar_color, skin, now, now),
            )
        return conn.execute(
            "SELECT * FROM users WHERE user_id = ?",
            (user_id,),
        ).fetchone()

def game_user_payload(row):
    return {
        "user_id": row["user_id"],
        "display_name": row["display_name"],
        "avatar_color": row["avatar_color"],
        "skin": row["skin"],
        "points": row["points"],
        "xp": row["xp"],
        "level": row["level"],
        "streak": row["streak"],
    }

def get_heart_rate_data(data):
    try:
        points = []
        for bucket in data.get("bucket", []):
            for dataset in bucket.get("dataset", []):
                for point in dataset.get("point", []):
                    val = point["value"][0].get("fpVal")
                    if val is not None:
                        points.append(val)
        return points
    except Exception as e:
        print(f"Error parsing heart rate: {e}")
        return []

def get_sleep_data_segments(data):
    try:
        segments = []
        for bucket in data.get("bucket", []):
            for dataset in bucket.get("dataset", []):
                for point in dataset.get("point", []):
                    segments.append(point)
        return segments
    except Exception as e:
        print(f"Error parsing sleep: {e}")
        return []

def get_total_minutes(time_str):
    try:
        time_str = str(time_str).strip().replace("-", ":")
        parts = time_str.split(":")

        hours = int(parts[0])
        minutes = int(parts[1])

        return hours * 60 + minutes

    except:
        print(f"Skipping invalid time: {time_str}")
        return None

def ensure_csv_headers():
    
    import os
    if not os.path.exists(FILE):
        with open(FILE, "w", newline="") as f:
            csv.writer(f).writerow(HEADERS)
        return
    
    with open(FILE, "r", newline="") as f:
        reader = csv.reader(f)
        existing_headers = next(reader, [])
    if "emotion" not in existing_headers:
        
        with open(FILE, "r", newline="") as f:
            rows = list(csv.reader(f))
        with open(FILE, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(HEADERS)
            for row in rows[1:]:  
                while len(row) < 5:
                    row.append("")
                row.append("")  
                writer.writerow(row)

def load_data():
    df = pd.read_csv(FILE)

    if "emotion" not in df.columns:
        df["emotion"] = ""

    df = df[df["item_id"].notna()]
    df["duration"] = pd.to_numeric(df["duration"], errors="coerce")
    df = df[df["event_type"] == "time_spent"]

    df["timestamp"] = pd.to_datetime(df["timestamp"])

    return df

def get_user_insights(df):

    time_spent = {
        "chatbot":0,
        "game":0,
        "journal":0,
        "planner":0
    }

    for _, row in df.iterrows():
        page = row["item_id"]
        time = row["duration"]

        if page == "/chatbot":
            time_spent["chatbot"] += time
        elif page == "/game":
            time_spent["game"] += time
        elif page == "/journal":
            time_spent["journal"] += time
        elif page == "/planner":
            time_spent["planner"] += time

    best = max(time_spent, key=time_spent.get)
    least = min(time_spent, key=time_spent.get)
    total = sum(time_spent.values())

    return time_spent, best, least, total

def classify_user(time_spent):

    if time_spent["journal"] > 40:
        return "Self Reflective"

    elif time_spent["game"] > 40:
        return "Stress Reliever"

    elif time_spent["planner"] > 40:
        return "Organized Learner"
    
    elif time_spent["chatbot"] > 40:
        return "Talkative Socializer"

    else:
        return "Balanced Explorer"
    
def predict_next(df):

    transitions = {}

    pages = df["item_id"].tolist()

    for i in range(len(pages)-1):
        curr = pages[i]
        next_page = pages[i+1]

        if curr not in transitions:
            transitions[curr] = {}

        transitions[curr][next_page] = transitions[curr].get(next_page, 0) + 1

    return transitions

def get_next_recommendation(transitions, current_page="/"):

    if current_page not in transitions:
        b = rd.randint(1, 4)
        match b:
            case 1:
                return "game"
            case 2:
                return "journal"
            case 3:
                return "planner"
            case 4:
                return "chatbot"
    next_pages = transitions[current_page]

    next_pages = {k: v for k, v in next_pages.items() if k != "/"}

    if not next_pages:
        b = rd.randint(1, 4)
        match b:
            case 1:
                return "game"
            case 2:
                return "journal"
            case 3:
                return "planner"
            case 4:
                return "chatbot"

    return max(next_pages, key=next_pages.get)

def get_time_preference(df):

    df["hour"] = df["timestamp"].dt.hour

    avg_hour = df["hour"].mean()

    if avg_hour < 12:
        return "morning"
    elif avg_hour < 18:
        return "afternoon"
    else:
        return "night"
    
def get_engagement_score(time_spent):

    score = (
        time_spent["journal"] * 2 +
        time_spent["planner"] * 2 +
        time_spent["chatbot"] * 1 -
        time_spent["game"] * 1
    )

    return max(score, 0)

def get_streak(df):
    if df.empty: return 0
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors='coerce')
    df = df.dropna(subset=["timestamp"])
    df["date"] = df["timestamp"].dt.date

    unique_days = sorted(df["date"].unique(), reverse=True)

    streak = 0
    prev_day = None

    for day in unique_days:
        if prev_day is None:
            streak += 1
        else:
            if (prev_day - day).days == 1:
                streak += 1
            else:
                break

        prev_day = day

    return streak

def get_mental_fitness_stats(df):
    
    streak = get_streak(df)
    

    total_activities = len(df[df["event_type"] == "time_spent"])

    level = int(1 + (total_activities / 5)**0.5)
    

    mood_counts = df[df["emotion"] != ""]["emotion"].value_counts().to_dict()
    top_emotions = sorted(mood_counts.items(), key=lambda x: x[1], reverse=True)[:3]
    

    xp_current = total_activities % 5
    xp_percent = int((xp_current / 5) * 100)
    
    return {
        "streak": streak,
        "level": level,
        "top_emotions": top_emotions,
        "xp_percent": xp_percent
    }

def mental_state(time_spent):

    if time_spent["game"] > time_spent["journal"]:
        return "needs_relaxation"

    elif time_spent["journal"] > time_spent["game"]:
        return "self_reflective"

    elif time_spent["chatbot"] > 30:
        return "needs_guidance"

    else:
        return "balanced"







def detect_emotion(text):
    
    try:

        prompt = f"Classify the emotion of this text into one word (e.g., joy, sadness, anger, fear, surprise, disgust, neutral): {text}"
        emotion = chat_with_gemini(prompt).strip().lower()

        emotion = ''.join(e for e in emotion if e.isalnum())
        return emotion if emotion else "neutral"
    except Exception as e:
        print(f"Gemini Emotion Detection Error: {e}")
        return "neutral"

def get_plan_from_emotion(emotion):

    if emotion in ["joy", "love", "surprise"]:
        return ["Gratitude Practice", "Mindful Breathing", "Light Physical Activity"]

    elif emotion in ["sadness"]:
        return ["Journaling", "Progressive Relaxation", "Comfort Activity"]

    elif emotion in ["anger", "fear"]:
        return ["Box Breathing ", "Self - Reflection", "Cooldown Activity"]

    else:
        return ["Light Learning", "Journalling", "Short Walk"]

@app.route("/manifest.json")
def manifest():
    return app.send_static_file("manifest.json")

@app.route("/service-worker.js")
def service_worker():
    return app.send_static_file("service-worker.js")

@app.route("/")
def home():
    try:
        data = pd.read_csv(FILE)

        filtered_df = data[data["duration"].notna()]

        time_spent = {
            "chatbot": 0,
            "game": 0,
            "journal": 0,
            "planner": 0
        }

        best_activity = "N/A"
        best_time = 0

        now = datetime.now()
        current_minutes = now.hour * 60 + now.minute

        best_diff = None
        best_activitytime = "N/A"

        for i in range(len(filtered_df)):

            activity = str(filtered_df.iloc[i, 2]).strip()
            
            try:
                duration = float(filtered_df.iloc[i, 3])
            except:
                continue

            if activity == "/chatbot":
                time_spent["chatbot"] += duration
            elif activity == "/game":
                time_spent["game"] += duration
            elif activity == "/journal":
                time_spent["journal"] += duration
            elif activity == "/planner":
                time_spent["planner"] += duration

            activity_time_raw = filtered_df.iloc[i, 4]

            if activity == "/":
                continue

            activity_minutes = get_total_minutes(activity_time_raw)

            if activity_minutes is None:
                continue

            diff = activity_minutes - current_minutes

            if best_diff is None or abs(diff) < abs(best_diff):
                best_diff = diff
                best_activitytime = activity

        for key in time_spent:
            if time_spent[key] > best_time:
                best_time = time_spent[key]
                best_activity = key


        gamification = get_mental_fitness_stats(filtered_df)

    except Exception as e:
        print("ERROR:", e)
        best_activity = "N/A"
        best_activitytime = "N/A"
        gamification = {"streak": 0, "level": 1, "top_emotions": [], "xp_percent": 0}

    ui_mode = session.get('ui_mode', 'drift')
    return render_template(
        "Oasis.html",
        best_activity=best_activity,
        best_activitytime=best_activitytime,
        gamification=gamification,
        ui_mode=ui_mode
    )

@app.route("/settings")
def settings():
    ui_mode = session.get('ui_mode', 'drift')
    return render_template("OasisSettings.html", ui_mode=ui_mode)

@app.route("/toggle-ui", methods=["POST"])
def toggle_ui():
    data = request.get_json()
    mode = data.get('mode', 'drift')
    session['ui_mode'] = mode
    return jsonify({"status": "success", "mode": mode})

@app.route("/oasis-home")
def oasis_home_embed():
    return home()




@app.route("/chatbot")
def chatbot():
    return render_template("OasisChatbot.html")

@app.route("/activities")
def activities():
    try:
        df = load_data()

        time_spent, best, least, total = get_user_insights(df)

        user_type = classify_user(time_spent)

        transitions = predict_next(df)
        next_rec = get_next_recommendation(transitions, current_page="/chatbot")

        time_pref = get_time_preference(df)

        score = get_engagement_score(time_spent)

        streak = get_streak(df)

        mental = mental_state(time_spent)

    except Exception as e:
        print("ERROR:", e)

        best = least = user_type = next_rec = time_pref = mental = "N/A"
        score = streak = 0

    return render_template(
        "OasisActivities.html",
        best=best,
        least=least,
        user_type=user_type,
        next_rec=next_rec,
        time_pref=time_pref,
        score=score,
        streak=streak,
        mental=mental
    )




@app.route("/game")
def game():
    return render_template("OasisGame.html")

@app.route("/journal")
def journal():
    return render_template("OasisJournal.html")

@app.route("/meditation")
def meditation():
    return render_template("meditation.html")

@app.route("/yoga")
def yoga():
    return render_template("yoga.html")


@app.route("/planner")
def planner():

    emotion = request.args.get("emotion", "neutral")
    activities = get_plan_from_emotion(emotion)

    return render_template(
        "OasisPlanner.html",
        emotion=emotion,
        activities=activities
    )


@app.route("/track", methods=["POST"])
def track():

    data = request.get_json(force=True)

    user_id = data.get("user_id")
    event_type = data.get("event_type")
    item_id = data.get("item_id")
    duration = data.get("duration", "")
    emotion = data.get("emotion", "")

    timestamp = datetime.now()

    with open(FILE, "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([user_id, event_type, item_id, duration, timestamp, emotion])

    return {"status": "success"}

@app.route("/oasis-watch")
def oasis_watch():
    return render_template("oasis_watch.html")

@app.route("/api/health_data")
def health_data():
    if 'credentials' not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    try:
        creds_data = session['credentials']
        credentials = Credentials(
            token=creds_data['token'],
            refresh_token=creds_data['refresh_token'],
            token_uri=creds_data['token_uri'],
            client_id=creds_data['client_id'],
            client_secret=creds_data['client_secret'],
            scopes=creds_data['scopes']
        )
        service = build("fitness", "v1", credentials=credentials)

        end_time = int(datetime.now().timestamp() * 1000)
        start_time = end_time - (7 * 24 * 60 * 60 * 1000)

        heart_raw = service.users().dataset().aggregate(
            userId="me",
            body={
                "aggregateBy": [{"dataTypeName": "com.google.heart_rate.bpm"}],
                "bucketByTime": {"durationMillis": 3600000},
                "startTimeMillis": start_time,
                "endTimeMillis": end_time
            }
        ).execute()

        sleep_raw = service.users().dataset().aggregate(
            userId="me",
            body={
                "aggregateBy": [{"dataTypeName": "com.google.sleep.segment"}],
                "bucketByTime": {"durationMillis": 86400000},
                "startTimeMillis": start_time,
                "endTimeMillis": end_time
            }
        ).execute()

        heart_points = get_heart_rate_data(heart_raw)
        if not isinstance(heart_points, (list, tuple)):
            heart_points = []
            
        sleep_count = len(get_sleep_data_segments(sleep_raw))

        avg_hr = sum(heart_points) / len(heart_points) if heart_points else 0
        
        if not heart_points:
             ai_response = "I haven't detected any recent heart rate data from your smartwatch. Once you sync your watch with Google Fit, I can provide a personalized stress analysis!"
        else:
            prompt = f"Analyze these heart rate data points: {heart_points}. The average heart rate is {round(avg_hr, 1)}. Provide a brief (2-3 sentence) empathetic insight about their stress level and suggest a mindful activity from Oasis (like Breathing, Journaling, or the 3D world)."
            try:
                ai_response = chat_with_gemini(prompt)
            except Exception:
                ai_response = "Connection to AI insight was interrupted. Take a deep breath and stay present!"

        return jsonify({
            "heart_rate_history": heart_points,
            "avg_heart_rate": round(avg_hr, 1),
            "sleep_segments": sleep_count,
            "stress_analysis": ai_response
        })
    except Exception as e:
        print(f"Health Data Error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/api/user_progress")
def user_progress():
    try:
        df = pd.read_csv(FILE)
        total_activities = len(df[df["event_type"] == "time_spent"])
        streak = get_streak(df)
        return jsonify({
            "total_activities": total_activities,
            "streak": streak
        })
    except Exception as e:
        print(f"User Progress Error: {e}")
        return jsonify({"total_activities": 0, "streak": 0})

@app.route("/detect_emotion", methods=["POST"])
def detect_emotion_api():
    try:
        data = request.get_json()
        text = data.get("text", "")

        emotion = detect_emotion(text)

        return jsonify({
            "status": "success",
            "emotion": emotion
        })

    except Exception as e:
        print("ERROR:", e)
        return jsonify({"status": "error"})
    
@app.route('/chat', methods=['POST'])
def chat():
    data = request.json
    user_input = data.get('message')
    user_id = data.get('user_id', '')
    persona = data.get('persona', 'friend')
    user_preferences = data.get('user_preferences', {})
    if not user_input:
        return jsonify({'error': 'No message provided'}), 400
    
    emotion = detect_emotion(user_input)
    
    
    try:
        timestamp = datetime.now()
        with open(FILE, "a", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([user_id, "emotion_detected", "/chatbot", "", timestamp, emotion])
    except Exception as log_err:
        print("Emotion log error:", log_err)

    try:
        response = get_oasis_response(user_input, emotion, persona, user_preferences)
        return jsonify({
            'response': response,
            'emotion': emotion
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/analyze_home', methods=['POST'])
def analyze_home():
    try:
        data = request.json or {}
        user_preferences = data.get('user_preferences', {})
        
        if not os.path.exists(FILE):
            return jsonify({"status": "success", "message": "Welcome to Oasis! Start using the app to see personalized AI insights here."})
            
        df = pd.read_csv(FILE)
        if df.empty:
            return jsonify({"status": "success", "message": "Welcome! I'm still learning about your routine. Keep exploring Oasis!"})
            
        if "emotion" not in df.columns:
            df["emotion"] = ""
        df = df.tail(200)

        log_text = "Time (Hour), Activity/Event, Emotion\n"
        emotion_time_patterns = []

        for _, row in df.iterrows():
            try:
                ts = pd.to_datetime(str(row['timestamp']), errors='coerce')
                if pd.isnull(ts):
                    continue
                hour = ts.hour
                time_label = f"{ts.strftime('%Y-%m-%d %H:%M')}"

                if hour < 6:
                    period = "late night"
                elif hour < 12:
                    period = "morning"
                elif hour < 17:
                    period = "afternoon"
                elif hour < 21:
                    period = "evening"
                else:
                    period = "night"

                event = str(row['event_type'])
                item = str(row['item_id'])
                emotion = str(row.get('emotion', '')).strip()
                duration = str(row['duration'])

                if event == "emotion_detected" and emotion and emotion != 'nan':
                    log_text += f"{time_label} ({period}) - Emotion: {emotion} on {item}\n"
                    emotion_time_patterns.append({"period": period, "emotion": emotion, "activity": item})
                elif event == "time_spent" and item != "/":
                    entry_emotion = emotion if emotion and emotion != 'nan' else "unknown"
                    log_text += f"{time_label} ({period}) - Spent {duration}s on {item}"
                    if entry_emotion != "unknown":
                        log_text += f" [emotion: {entry_emotion}]"
                    log_text += "\n"
            except Exception:
                continue

        prefs_context = ""
        if user_preferences and isinstance(user_preferences, dict):
            prefs_context = "\nUser Personality & Preferences:\n"
            for key, val in user_preferences.items():
                prefs_context += f"- {key.replace('_', ' ').capitalize()}: {val}\n"

        prompt = f"Based on the following activity logs for a user, provide a 1-2 sentence personalized insight or encouragement for their wellness journey in Oasis. If you notice patterns (like high stress in the morning), mention them gently. Use the context of their preferences if available: {prefs_context}\n\nLogs:\n{log_text}"
        response_text = chat_with_gemini(prompt)

        return jsonify({"status": "success", "message": response_text})

    except Exception as e:
        print("Analyze Home Error:", e)
        return jsonify({"status": "error", "message": "I hope you are having a wonderful, peaceful day."})

@app.route('/authorize')
def authorize():
    if not os.path.exists(CLIENT_SECRETS_FILE):
        return "ERROR: credentials.json not found in project directory.", 404
    

    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE,
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI
    )
    
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true'
    )
    

    session['state'] = state
    
    return redirect(authorization_url)

@app.route('/oauth2callback')
def oauth2callback():

    state = session.get('state')
    if not state:
        return "ERROR: OAuth state missing from session.", 400
        
    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE,
        scopes=SCOPES,
        state=state,
        redirect_uri=REDIRECT_URI
    )
    

    flow.fetch_token(authorization_response=request.url)
    
    credentials = flow.credentials
    session['credentials'] = {
        'token': credentials.token,
        'refresh_token': credentials.refresh_token,
        'token_uri': credentials.token_uri,
        'client_id': credentials.client_id,
        'client_secret': credentials.client_secret,
        'scopes': credentials.scopes
    }
    
    return redirect(url_for('planner', synced='true'))

@app.route('/sync_to_calendar', methods=['POST'])
def sync_to_calendar():
    from flask import session
    if 'credentials' not in session:
        return jsonify({"status": "unauthorized"})
    
    try:
        data = request.get_json()
        activities = data.get('activities', [])
        
        creds_data = session['credentials']
        credentials = Credentials(
            token=creds_data['token'],
            refresh_token=creds_data['refresh_token'],
            token_uri=creds_data['token_uri'],
            client_id=creds_data['client_id'],
            client_secret=creds_data['client_secret'],
            scopes=creds_data['scopes']
        )
        
        service = build('calendar', 'v3', credentials=credentials)
        
        now = datetime.now()
        
        for i, activity in enumerate(activities):
            start_time = now + timedelta(hours=(i+1))
            end_time = start_time + timedelta(minutes=30)
            
            event = {
                'summary': f'Oasis: {activity}',
                'description': f'A mindful activity planned by Oasis Assistant.',
                'start': {
                    'dateTime': start_time.isoformat(),
                    'timeZone': 'UTC',
                },
                'end': {
                    'dateTime': end_time.isoformat(),
                    'timeZone': 'UTC',
                },
                'reminders': {
                    'useDefault': True,
                },
            }
            
            service.events().insert(calendarId='primary', body=event).execute()
            
        return jsonify({"status": "success"})
    except Exception as e:
        print(f"Sync Error: {e}")
        return jsonify({"status": "error", "message": str(e)})

@app.route('/speech-to-text', methods=['POST'])
def speech_to_text():
    if 'audio' not in request.files:
        return jsonify({'error': 'No audio file provided'}), 400
    
    audio_file = request.files['audio']
    
    try:

        with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as tmp:
            audio_file.save(tmp.name)
            tmp_path = tmp.name

        try:

            with open(tmp_path, "rb") as f:
                audio_bytes = f.read()

            print(f"STT: Received {len(audio_bytes)} bytes of audio.")


            model_ids = ['gemini-2.0-flash', 'gemini-2.5-flash', 'models/gemini-2.5-flash']
            response = None
            
            for mid in model_ids:
                try:
                    print(f"STT: Trying {mid}...")
                    response = genai_client_v2.models.generate_content(
                        model=mid,
                        contents=[
                            types.Part.from_bytes(data=audio_bytes, mime_type='audio/webm'),
                            "Transcribe this audio. Output ONLY the transcription."
                        ]
                    )
                    if response and response.text:
                        break
                except Exception as e_mid:
                    print(f"STT: {mid} failed: {e_mid}")

            if not response or not (hasattr(response, 'text') and response.text):

                print("STT: v2 failed, using v1 fallback...")
                v1_model = genai_v1.GenerativeModel('gemini-2.5-flash')
                response = v1_model.generate_content([
                    "Transcribe this audio. Output ONLY the transcription.",
                    {'mime_type': 'audio/webm', 'data': audio_bytes}
                ])
            
            os.remove(tmp_path)
            
            transcription = ""
            if response:
                try:
                    transcription = response.text.strip()
                except:
                    pass

            print(f"STT Transcription: '{transcription}'")
            return jsonify({'text': transcription})
            
        except Exception as e:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            raise e
            
    except Exception as e:
        print(f"Gemini STT Error: {e}")
        return jsonify({'error': str(e)}), 500

async def generate_gemini_voice(text):
    

    model_id = 'gemini-2.0-flash'
    config = types.LiveConnectConfig(
        response_modalities=['AUDIO'],
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(
                    voice_name='Charon'
                )
            )
        )
    )
    
    audio_chunks = []
    async with genai_client_v2.aio.live.connect(model=model_id, config=config) as session:
        await session.send_client_content(
            turns=[types.Content(parts=[types.Part.from_text(text=text)])],
            turn_complete=True
        )
        
        async for response in session.receive():
            if response.data:
                audio_chunks.append(response.data)
            if response.server_content and response.server_content.turn_complete:
                break
                
    return b"".join(audio_chunks)

@app.route('/text-to-speech', methods=['POST'])
def text_to_speech():
    data = request.json
    text = data.get('text')
    if not text:
        return jsonify({'error': 'No text provided'}), 400
    
    try:

        import asyncio

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
        audio_content = loop.run_until_complete(generate_gemini_voice(f"Speak this exactly: {text}"))
        
        if not audio_content:
            raise Exception("No audio data generated")
            
        return Response(audio_content, mimetype="audio/wav")
        
    except Exception as e:
        print(f"Gemini TTS Error: {e}")
        return jsonify({'error': str(e)}), 500





@app.route("/counsellor")
def counsellor_portal():
    return render_template("CounsellorPortal.html")

@app.route("/api/counsellor/data")
def counsellor_data():
    try:
        df = pd.read_csv(FILE)
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        

        mood_map = {"joy": 100, "neutral": 70, "sadness": 40, "anger": 30, "fear": 30}
        emotions = df[df["emotion"].isin(mood_map.keys())]["emotion"]
        wellbeing_score = int(emotions.map(mood_map).mean()) if not emotions.empty else 75
        

        alerts = []
        user_groups = df.groupby("user_id")
        
        for user_id, group in user_groups:
            group = group.sort_values("timestamp")
            

            if len(group) >= 2:
                last_two = group.tail(2)["emotion"].tolist()
                if last_two[0] == "joy" and last_two[1] in ["sadness", "anger", "fear"]:
                    alerts.append({
                        "user_id": user_id,
                        "risk": "High",
                        "type": "Sudden Mood Drop",
                        "message": f"Student {user_id} dropped from joy to {last_two[1]}.",
                        "actions": ["Direct intervention", "Send wellness check", "Schedule consultation"]
                    })
            

            neg_count = group[group["emotion"].isin(["sadness", "anger", "fear"])].shape[0]
            if neg_count > 5:
                 alerts.append({
                        "user_id": user_id,
                        "risk": "Medium",
                        "type": "Persistent Negative Mood",
                        "message": f"Student {user_id} has logged multiple negative entries recently."
                    })


        df["date"] = df["timestamp"].dt.date
        daily_moods = df.groupby("date")["emotion"].apply(lambda x: x.map(mood_map).mean()).reset_index()
        daily_moods["date"] = daily_moods["date"].apply(lambda x: x.strftime("%Y-%m-%d"))
        trends = daily_moods.to_dict(orient="records")


        top_issues = df[df["emotion"].isin(["sadness", "anger", "fear"])]["item_id"].value_counts().head(3).to_dict()

        return jsonify({
            "wellbeing_score": wellbeing_score,
            "alerts": alerts,
            "trends": trends,
            "top_issues": top_issues
        })
    except Exception as e:
        print("Counsellor Data Error:", e)
        return jsonify({"error": str(e)}), 500





@app.route("/vector-dashboard")
def vector_dashboard():
    
    return render_template("vector_dashboard.html")


@app.route("/api/user_vector")
def api_user_vector():
    
    user_id = request.args.get("user_id", "").strip()
    window_days = int(request.args.get("window_days", 7))

    if not user_id:

        ids = get_all_user_ids(FILE)
        return jsonify({"user_ids": ids})

    try:
        result = compute_user_vector(user_id, FILE, window_days=window_days)
        return jsonify(result)
    except Exception as e:
        print(f"Vector API error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/vector_update", methods=["POST"])
def api_vector_update():
    
    data = request.get_json(force=True)
    user_id    = data.get("user_id", "")
    event_type = data.get("event_type", "")
    item_id    = data.get("item_id", "")
    duration   = data.get("duration", "")
    emotion    = data.get("emotion", "")
    old_vector = data.get("old_vector", None)


    timestamp = datetime.now()
    try:
        with open(FILE, "a", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([user_id, event_type, item_id, duration, timestamp, emotion])
    except Exception as e:
        print(f"Vector update CSV write error: {e}")


    try:
        result = compute_user_vector(user_id, FILE, window_days=7)


        if old_vector and isinstance(old_vector, list) and len(old_vector) == 6:
            new_event = {"event_type": event_type, "item_id": item_id,
                         "duration": duration, "emotion": emotion}
            result["incremental_vector"] = incremental_update(old_vector, new_event)

        return jsonify(result)
    except Exception as e:
        print(f"Vector update error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/all_user_ids")
def api_all_user_ids():
    
    ids = get_all_user_ids(FILE)
    return jsonify({"user_ids": ids})




ensure_csv_headers()





@app.route("/recommend")
def recommend_page():
    
    return render_template("OasisRecommend.html")


@app.route("/api/recommendations")
def api_recommendations():
    
    user_id     = request.args.get("user_id", "").strip()
    window_days = int(request.args.get("window_days", 365))
    top_k       = int(request.args.get("top_k", 3))

    try:
        vec_result = compute_user_vector(user_id, FILE, window_days=window_days)
        user_vec   = vec_result["vector"]
        result     = get_recommendations(user_vec, top_k=top_k)
        result["vector_meta"] = vec_result["dimensions"]
        return jsonify(result)
    except Exception as e:
        print(f"Recommendations API error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/feedback", methods=["POST"])
def api_feedback():
    
    data        = request.get_json(force=True)
    user_id     = data.get("user_id", "")
    activity_id = data.get("activity_id", "")
    feedback    = data.get("feedback", "")
    current_vec = data.get("current_vector", None)

    try:
        new_weight = apply_feedback(activity_id, feedback)
        event_type = "complete" if feedback == "complete" else "skip"
        timestamp  = datetime.now()
        with open(FILE, "a", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([user_id, event_type, activity_id, "", timestamp, ""])

        updated_vec = None
        if current_vec and isinstance(current_vec, list) and len(current_vec) == 6:
            if feedback == "complete":
                updated_vec = apply_activity_effect(current_vec, activity_id)
            else:
                updated_vec = current_vec

        return jsonify({
            "status":         "success",
            "feedback":       feedback,
            "activity_id":    activity_id,
            "new_weight":     new_weight,
            "updated_vector": updated_vec,
        })
    except Exception as e:
        print(f"Feedback API error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/api/award_points", methods=["POST"])
def award_points():
    try:
        data = request.get_json()
        user_id = data.get("user_id")
        amount = data.get("amount", 100)
        reason = data.get("reason", "Counsellor Reward")
        timestamp = datetime.now()
        with open(FILE, "a", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([user_id, "reward", reason, amount, timestamp, "joy"])
        return jsonify({"status": "success", "message": f"Awarded {amount} points to {user_id}"})
    except Exception as e:
        print("Award Points Error:", e)
        return jsonify({"status": "error"}), 500

@app.route("/api/user_data/<user_id>")
def get_user_data(user_id):
    try:
        df = pd.read_csv(FILE)
        user_df = df[df["user_id"] == user_id]
        rewards = user_df[user_df["event_type"] == "reward"]
        total_points = pd.to_numeric(rewards["duration"], errors='coerce').sum() if not rewards.empty else 0
        total_points += 100 
        return jsonify({
            "user_id": user_id,
            "points": float(total_points),
            "level": int(1 + (len(user_df) / 5)**0.5),
            "streak": get_streak(user_df) if not user_df.empty else 0
        })
    except Exception as e:
        print("Get User Data Error:", e)
        return jsonify({"status": "error"}), 500

@app.route("/api/game/profile", methods=["GET", "POST"])
def game_profile():
    try:
        if request.method == "POST":
            data = request.get_json(force=True)
        else:
            data = request.args

        user_id = str(data.get("user_id", "")).strip()
        if not user_id:
            return jsonify({"error": "Missing user_id"}), 400

        display_name = str(data.get("display_name", "Explorer")).strip() or "Explorer"
        avatar_color = str(data.get("avatar_color", "#8b5cf6")).strip() or "#8b5cf6"
        skin = str(data.get("skin", "oasis")).strip() or "oasis"
        row = upsert_game_user(user_id, display_name, avatar_color, skin)

        with get_db() as conn:
            completed = conn.execute(
                "SELECT * FROM progress_events WHERE user_id = ? ORDER BY created_at DESC LIMIT 5",
                (user_id,),
            ).fetchall()

        payload = game_user_payload(row)
        payload["recent_progress"] = [dict(item) for item in completed]
        payload["missions"] = DEFAULT_MISSIONS
        return jsonify(payload)
    except Exception as e:
        print("Game Profile Error:", e)
        return jsonify({"error": str(e)}), 500

@app.route("/api/game/progress", methods=["POST"])
def game_progress():
    try:
        data = request.get_json(force=True)
        user_id = str(data.get("user_id", "")).strip()
        mission_id = str(data.get("mission_id", "")).strip()
        if not user_id or not mission_id:
            return jsonify({"error": "Missing user_id or mission_id"}), 400

        mission = DEFAULT_MISSIONS.get(mission_id, {
            "title": data.get("mission_title", "Oasis Mission"),
            "description": "",
            "points": int(data.get("points", 25)),
            "emotion": data.get("mood", "neutral"),
        })
        display_name = str(data.get("display_name", "Explorer")).strip() or "Explorer"
        avatar_color = str(data.get("avatar_color", "#8b5cf6")).strip() or "#8b5cf6"
        skin = str(data.get("skin", "oasis")).strip() or "oasis"
        note = str(data.get("note", "")).strip()
        points = int(mission.get("points", 25))
        mood = str(data.get("mood", mission.get("emotion", "neutral")))
        now = datetime.now()

        upsert_game_user(user_id, display_name, avatar_color, skin)
        with get_db() as conn:
            row = conn.execute("SELECT points, xp FROM users WHERE user_id = ?", (user_id,)).fetchone()
            new_points = int(row["points"]) + points
            new_xp = int(row["xp"]) + points * 2
            new_level = int(1 + (new_xp / 300) ** 0.5)
            conn.execute(
                "UPDATE users SET points = ?, xp = ?, level = ?, updated_at = ? WHERE user_id = ?",
                (new_points, new_xp, new_level, now.isoformat(), user_id),
            )
            conn.execute(
                "INSERT INTO progress_events (user_id, mission_id, mission_title, points, mood, note, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (user_id, mission_id, mission["title"], points, mood, note, now.isoformat()),
            )
            updated = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()

        try:
            with open(FILE, "a", newline="") as f:
                writer = csv.writer(f)
                writer.writerow([user_id, "complete", f"3d:{mission_id}", points, now, mood])
        except Exception as csv_err:
            print("Game progress CSV log error:", csv_err)

        return jsonify({
            "status": "success",
            "mission": mission,
            "profile": game_user_payload(updated),
        })
    except Exception as e:
        print("Game Progress Error:", e)
        return jsonify({"error": str(e)}), 500

@app.route("/api/game/chat", methods=["POST"])
def game_chat():
    try:
        data = request.get_json(force=True)
        user_id = str(data.get("user_id", "")).strip()
        message = str(data.get("message", "")).strip()
        if not user_id or not message:
            return jsonify({"error": "Missing user_id or message"}), 400
        
        position = data.get("position", {}) or {}
        x = float(position.get("x", 0))
        y = float(position.get("y", 0))
        z = float(position.get("z", 0))
        now = datetime.now()

        with get_db() as conn:
            conn.execute(
                "INSERT INTO chat_messages (sender_id, message, x, y, z, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (user_id, message, x, y, z, now.isoformat()),
            )
        
        return jsonify({"status": "success"})
    except Exception as e:
        print("Game Chat Error:", e)
        return jsonify({"error": str(e)}), 500

@app.route("/api/game/presence", methods=["GET", "POST"])
def game_presence():
    try:
        now = datetime.now()
        current_x, current_y, current_z = 0, 0, 0
        if request.method == "POST":
            data = request.get_json(force=True)
            user_id = str(data.get("user_id", "")).strip()
            if not user_id:
                return jsonify({"error": "Missing user_id"}), 400
            display_name = str(data.get("display_name", "Explorer")).strip() or "Explorer"
            avatar_color = str(data.get("avatar_color", "#8b5cf6")).strip() or "#8b5cf6"
            skin = str(data.get("skin", "oasis")).strip() or "oasis"
            level = int(data.get("level", 1))
            position = data.get("position", {}) or {}
            current_x = float(position.get("x", 0))
            current_y = float(position.get("y", 0))
            current_z = float(position.get("z", 0))

            upsert_game_user(user_id, display_name, avatar_color, skin)
            with get_db() as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO presence (user_id, display_name, avatar_color, skin, x, y, z, level, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (user_id, display_name, avatar_color, skin, current_x, current_y, current_z, level, now.isoformat()),
                )

        current_user = request.args.get("user_id", "").strip()
        
        if request.method == "GET" and current_user:
            with get_db() as conn:
                p_row = conn.execute("SELECT x, y, z FROM presence WHERE user_id = ?", (current_user,)).fetchone()
                if p_row:
                    current_x, current_y, current_z = p_row["x"], p_row["y"], p_row["z"]

        cutoff = (now - timedelta(seconds=45)).isoformat()
        chat_cutoff = (now - timedelta(seconds=30)).isoformat()
        chat_radius = 15.0

        with get_db() as conn:
            conn.execute("DELETE FROM presence WHERE updated_at < ?", (cutoff,))
            conn.execute("DELETE FROM chat_messages WHERE created_at < ?", (chat_cutoff,))
            
            rows = conn.execute(
                "SELECT * FROM presence WHERE user_id != ?",
                (current_user,),
            ).fetchall()

            all_messages = conn.execute(
                "SELECT * FROM chat_messages WHERE sender_id != ? AND created_at > ?",
                (current_user, chat_cutoff),
            ).fetchall()
            
            nearby_messages = []
            for msg in all_messages:
                dx = msg["x"] - current_x
                dy = msg["y"] - current_y
                dz = msg["z"] - current_z
                dist = (dx*dx + dy*dy + dz*dz)**0.5
                if dist < chat_radius:
                    nearby_messages.append({
                        "id": msg["id"],
                        "message": msg["message"],
                        "created_at": msg["created_at"],
                        "sender_id": "Stranger"
                    })

        return jsonify({
            "online": [
                {
                    "id": row["user_id"],
                    "name": row["display_name"],
                    "level": row["level"],
                    "avatar": {"color": row["avatar_color"], "skin": row["skin"]},
                    "position": {"x": row["x"], "y": row["y"], "z": row["z"]},
                }
                for row in rows
            ],
            "messages": nearby_messages
        })
    except Exception as e:
        print("Game Presence Error:", e)
        return jsonify({"error": str(e)}), 500

init_game_db()

if __name__ == "__main__":
    # Use environment variable PORT for Fly.io; default to 5000 for local dev
    import os
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)