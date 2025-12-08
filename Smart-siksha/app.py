from flask import Flask, render_template, request, jsonify, redirect, session, url_for
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
import csv, os, subprocess, re, unicodedata, hashlib, threading, time
from fpdf import FPDF
import numpy as np
import textwrap
import random
from enum import Enum
import requests
import json
import sqlite3
from datetime import datetime

app = Flask(__name__)
CORS(app)
app.secret_key = 'your_secret_key_here'

CSV_PATH = "csv/users.csv"
QUIZ_DB_PATH = "csv/quizzes.db"
os.makedirs("csv", exist_ok=True)
os.makedirs("static/generated_pdfs", exist_ok=True)
os.makedirs("static/generated_videos", exist_ok=True)
os.makedirs("static/generated_audio", exist_ok=True)
os.makedirs("static/uploaded_books", exist_ok=True)

def init_quiz_database():
    """Initialize SQLite database for storing quizzes"""
    conn = sqlite3.connect(QUIZ_DB_PATH)
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS saved_quizzes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_name TEXT,
            topic TEXT,
            user_class TEXT,
            quiz_data TEXT,
            score INTEGER,
            total_questions INTEGER,
            percentage REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP
        )
    ''')

    conn.commit()
    conn.close()
    print("✅ Quiz database initialized")

init_quiz_database()

# Global variables for video generation
video_generation_progress = {}

# Video generation classes and functions
class TransitionType(Enum):
    FADE = "fade"
    SLIDE_LEFT = "slide_left"
    SLIDE_RIGHT = "slide_right"
    SLIDE_UP = "slide_up"
    SLIDE_DOWN = "slide_down"
    ZOOM_IN = "zoom_in"
    ZOOM_OUT = "zoom_out"
    CROSS_FADE = "cross_fade"
    WIPE_LEFT = "wipe_left"
    WIPE_RIGHT = "wipe_right"

# Video settings for 16:9 aspect ratio
VIDEO_WIDTH = 1280
VIDEO_HEIGHT = 720
TRANSITION_DURATION = 0.5
TRANSITION_FPS = 24

# ----------------- Gamification Data Stores -----------------
# These reset when server restarts (good enough for hackathon demo)
user_points = {}
user_badges = {}

# -------------------- ROUTES --------------------

@app.route("/")
def landing():
    return render_template("sign_up_page.html")

@app.route("/interests")
def interests():
    return render_template("interests.html")

@app.route("/home")
def home():
    username = session.get("username")
    return render_template("home.html", user_badges=user_badges.get(username, []))


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("landing"))

@app.route("/options")
def options():
    topic = session.get("current_topic", "Pythagorean Theorem")
    name = session.get("user_name", "User")
    return render_template("options.html", topic=topic, name=name)
@app.route("/previous_chats")
def previous_chats():
    return render_template("previous_chats.html")

@app.route("/notes")
def notes():
    topic = session.get("current_topic", "Pythagorean Theorem")
    name = session.get("user_name", "User")
    interests = session.get("user_interests", "science")
    interest_hash = get_interest_hash(interests.split(","))
    folder_name = f"{topic.replace(' ', '_')}__{interest_hash}"
    pdf_path = f"/static/generated_pdfs/{folder_name}/notes.pdf"
    return render_template("notes.html", topic=topic, name=name, pdf_path=pdf_path)

@app.route("/video")
def video():
    topic = session.get("current_topic", "Pythagorean Theorem")
    name = session.get("user_name", "User")
    interests = session.get("user_interests", "science")
    interest_hash = get_interest_hash(interests.split(","))
    folder_name = f"{topic.replace(' ', '_')}__{interest_hash}"
    pdf_path = f"/static/generated_pdfs/{folder_name}/notes.pdf"
    video_path = f"/static/generated_videos/{folder_name}/final_output_video.mp4"
    return render_template("video.html", topic=topic, name=name, pdf_path=pdf_path, video_path=video_path)

@app.route("/set_topic", methods=["POST"])
def set_topic():
    topic = request.json.get("topic")
    if topic:
        session["current_topic"] = topic
        return jsonify({"message": "Topic set"}), 200
    return jsonify({"error": "No topic provided"}), 400

@app.route("/profile")
def profile():
    interests_raw = session.get("user_interests", [])
    if isinstance(interests_raw, str):
        interests = [i.strip() for i in interests_raw.split(",") if i.strip()]
    else:
        interests = interests_raw

    return render_template(
        "profile.html",
        name=session.get("user_name"),
        age=session.get("user_age"),
        contact=session.get("user_contact"),
        gender=session.get("user_gender"),
        user_class=session.get("user_class"),
        interests=interests
    )
@app.route("/counselling")
def counselling():
    return render_template("counselling.html")

@app.route("/quiz")
def quiz():
    topic = session.get("current_topic", "General Topic")
    name = session.get("user_name", "User")

    last_quiz = get_last_quiz(name, topic)

    return render_template("quiz.html", topic=topic, name=name, last_quiz=last_quiz)

def get_last_quiz(user_name, topic):
    """Get the last saved quiz for a user and topic"""
    try:
        conn = sqlite3.connect(QUIZ_DB_PATH)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT quiz_data, score, total_questions, percentage, created_at, completed_at
            FROM saved_quizzes
            WHERE user_name = ? AND topic = ?
            ORDER BY created_at DESC
            LIMIT 1
        ''', (user_name, topic))

        result = cursor.fetchone()
        conn.close()

        if result:
            quiz_data, score, total_questions, percentage, created_at, completed_at = result
            return {
                'quiz_data': json.loads(quiz_data),
                'score': score,
                'total_questions': total_questions,
                'percentage': percentage,
                'created_at': created_at,
                'completed_at': completed_at,
                'has_quiz': True
            }
        else:
            return {'has_quiz': False}

    except Exception as e:
        print(f"❌ Error getting last quiz: {e}")
        return {'has_quiz': False}

def save_quiz_to_db(user_name, topic, user_class, quiz_data, score=None, total_questions=None, percentage=None):
    """Save quiz to database"""
    try:
        conn = sqlite3.connect(QUIZ_DB_PATH)
        cursor = conn.cursor()

        if score is not None:
            # Update existing quiz with results
            cursor.execute('''
                UPDATE saved_quizzes
                SET score = ?, total_questions = ?, percentage = ?, completed_at = CURRENT_TIMESTAMP
                WHERE user_name = ? AND topic = ? AND completed_at IS NULL
                ORDER BY created_at DESC
                LIMIT 1
            ''', (score, total_questions, percentage, user_name, topic))
        else:
            # Insert new quiz
            cursor.execute('''
                INSERT INTO saved_quizzes (user_name, topic, user_class, quiz_data)
                VALUES (?, ?, ?, ?)
            ''', (user_name, topic, user_class, json.dumps(quiz_data)))

        conn.commit()
        conn.close()
        print(f"✅ Quiz saved for {user_name} - {topic}")
        return True

    except Exception as e:
        print(f"❌ Error saving quiz: {e}")
        return False

@app.route("/get_saved_quizzes", methods=["GET"])
def get_saved_quizzes():
    """Get all saved quizzes for the current user"""
    user_name = session.get("user_name", "User")

    try:
        conn = sqlite3.connect(QUIZ_DB_PATH)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT topic, score, total_questions, percentage, created_at, completed_at
            FROM saved_quizzes
            WHERE user_name = ? AND completed_at IS NOT NULL
            ORDER BY completed_at DESC
            LIMIT 20
        ''', (user_name,))

        results = cursor.fetchall()
        conn.close()

        saved_quizzes = []
        for result in results:
            topic, score, total_questions, percentage, created_at, completed_at = result
            saved_quizzes.append({
                'topic': topic,
                'score': score,
                'total_questions': total_questions,
                'percentage': round(percentage, 1),  # Round percentage for display
                'created_at': created_at,
                'completed_at': completed_at
            })

        print(f"✅ Retrieved {len(saved_quizzes)} saved quizzes for {user_name}")
        return jsonify({'saved_quizzes': saved_quizzes})

    except Exception as e:
        print(f"❌ Error getting saved quizzes: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e), 'saved_quizzes': []}), 500

@app.route("/watch/<topic>")
def watch_video(topic):
    username = session.get("username")
    if username:
        award_points(username, "video")
        check_and_award_badges(username)
    return f"Video for {topic} shown. Points: {user_points.get(username, 0)}"

@app.route("/download_notes/<topic>")
def download_notes(topic):
    username = session.get("username")
    if username:
        award_points(username, "notes")
        check_and_award_badges(username)
    return f"Notes downloaded for {topic}. Points: {user_points.get(username, 0)}"

@app.route("/leaderboard")
def leaderboard():
    sorted_users = sorted(user_points.items(), key=lambda x: x[1], reverse=True)
    leaderboard_data = []
    for idx, (user, pts) in enumerate(sorted_users, start=1):
        badges = user_badges.get(user, [])
        leaderboard_data.append((idx, user, pts, badges))
    return render_template("leaderboard.html", leaderboard=leaderboard_data)


# -----------------------------------------------------------------------------------------------------------------------------------------.

def award_points(username, action):
    points_map = {"video": 10, "notes": 5, "quiz_pass": 20}
    user_points[username] = user_points.get(username, 0) + points_map.get(action, 0)

def award_badge(username, badge):
    if username not in user_badges:
        user_badges[username] = []
    if badge not in user_badges[username]:
        user_badges[username].append(badge)

def check_and_award_badges(username):
    points = user_points.get(username, 0)
    if points >= 50 and "Learner" not in user_badges.get(username, []):
        award_badge(username, "Learner")
    if points >= 100 and "Achiever" not in user_badges.get(username, []):
        award_badge(username, "Achiever")

def adaptive_recommendation(score, topic):
    if score < 50:
        return f"Recommend simpler video for {topic}"
    elif score < 80:
        return f"Recommend revision quiz for {topic}"
    else:
        return f"Recommend challenge questions for {topic}"


# -----------------------------------------------------------------------------------------------------------------------------------------

# --- QUIZ: 10 Qs + open-ended question, robust parsing & caching ---

def _normalize_text(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())

def _shuffle_options_preserve_answer(q: dict) -> dict:
    """
    Shuffle options but keep a correct answer by updating answer_index accordingly.
    """
    opts = q.get("options", [])[:]
    if not isinstance(opts, list) or len(opts) != 4:
        return q

    correct_idx = q.get("answer_index", 0)
    if not isinstance(correct_idx, int) or not (0 <= correct_idx < len(opts)):
        return q

    correct_value = opts[correct_idx]
    random.shuffle(opts)
    new_idx = opts.index(correct_value)
    q["options"] = opts
    q["answer_index"] = new_idx
    return q

def _gen_unique_math_question() -> dict:
    """
    Generate a single unique arithmetic question with plausible distractors.
    Operations: +, -, ×, ÷, squares, square roots, simple fractions.
    """
    op = random.choice(["add", "sub", "mul", "div", "sq", "sqrt"])
    a = random.randint(2, 20)
    b = random.randint(2, 20)

    if op == "add":
        question = f"What is {a} + {b}?"
        correct = a + b
    elif op == "sub":
        # ensure non-negative results for middle school
        if b > a:
            a, b = b, a
        question = f"What is {a} - {b}?"
        correct = a - b
    elif op == "mul":
        question = f"What is {a} × {b}?"
        correct = a * b
    elif op == "div":
        # make divisible
        correct = random.randint(2, 12)
        a = correct * b
        question = f"What is {a} ÷ {b}?"
    elif op == "sq":
        n = random.randint(2, 15)
        question = f"What is {n}²?"
        correct = n * n
    else:  # "sqrt"
        n = random.randint(2, 15)
        val = n * n
        question = f"What is the square root of {val}?"
        correct = n

    # plausible distractors near correct
    distractors = set()
    candidates = [correct - 2, correct - 1, correct + 1, correct + 2, correct + 3, correct - 3]
    for c in candidates:
        if c != correct and c >= 0:
            distractors.add(c)
        if len(distractors) == 3:
            break
    while len(distractors) < 3:
        distractors.add(correct + random.randint(4, 8))

    options = [str(correct)] + [str(x) for x in list(distractors)[:3]]
    random.shuffle(options)
    answer_index = options.index(str(correct))

    return {
        "question": question,
        "options": options,
        "answer_index": answer_index,
    }

def _fill_unique_questions(questions: list, topic: str, user_class: str, used_set: set) -> list:
    """
    Ensure we return exactly 10 unique, valid questions.
    - Deduplicate by normalized question text.
    - Shuffle options and correct indices.
    - Fill missing with math generator if topic is math-like; otherwise, generate safe templated Qs.
    - Avoid cross-generation duplicates using used_set per topic.
    """
    # Seed some randomness so successive generations differ
    random.seed(time.time())

    out = []
    seen = set()

    def push(q):
        qt = _normalize_text(q.get("question", ""))
        if not qt or qt in seen or qt in used_set:
            return False
        opts = q.get("options")
        ai = q.get("answer_index")
        if not isinstance(opts, list) or len(opts) != 4 or not isinstance(ai, int) or not (0 <= ai < 4):
            return False
        out.append(_shuffle_options_preserve_answer(q))
        seen.add(qt)
        return True

    # 1) Keep valid and unique from incoming list
    for q in questions or []:
        if len(out) == 10:
            break
        push(q)

    # 2) Fill to 10 with generated questions
    topic_lower = (topic or "").lower()
    is_math = any(k in topic_lower for k in ["math", "algebra", "geometry", "arithmetic", "number", "fraction", "equation"])

    attempts = 0
    while len(out) < 10 and attempts < 200:
        attempts += 1
        if is_math:
            q = _gen_unique_math_question()
            push(q)
        else:
            # Safe templated general question with a clear correct option
            base = random.choice([
                (f"Which statement is true about {topic}?", ["It has real-world applications", "It is never used", "It has no practical value", "Only experts can learn it"], 0),
                (f"Why is {topic} important for {user_class} students?", ["It builds core understanding", "It is optional trivia", "It replaces all subjects", "It has no benefits"], 0),
                (f"What is a common way to learn {topic}?", ["Practice and examples", "Avoid studying", "Ignore feedback", "Memorize random facts"], 0),
                (f"Which option best describes {topic}?", ["A set of key concepts", "A single fixed rule", "A random idea", "A secret method"], 0),
                (f"How can {topic} connect to daily life?", ["Through practical examples", "It cannot", "Only in labs", "Only on exams"], 0),
            ])
            q = {
                "question": base[0],
                "options": base[1][:],
                "answer_index": base[2],
            }
            push(q)

    # If still short, last resort: duplicate-safe math generators
    while len(out) < 10:
        q = _gen_unique_math_question()
        if push(q):
            continue

    return out

def _update_used_questions_session(topic: str, new_questions: list):
    used_map = session.get("used_questions", {})
    used_list = used_map.get(topic, [])
    for q in new_questions:
        used_list.append(_normalize_text(q.get("question", "")))
    # keep last N to prevent cookie from growing too large
    used_map[topic] = used_list[-200:]
    session["used_questions"] = used_map

@app.route("/generate_quiz", methods=["POST"])
def generate_quiz():
    topic = session.get("current_topic", "General Knowledge")
    user_class = session.get("user_class", "middle school")
    user_name = session.get("user_name", "User")
    data = request.get_json() or {}
    force_refresh = data.get("force", False)

    cache = session.get("quiz_cache")
    if cache and cache.get("topic") == topic and not force_refresh:
        return jsonify(cache["payload"])

    print(f"🧠 Generating quiz for topic: {topic}, class: {user_class}")

    prompt = f"""Generate exactly 10 multiple-choice quiz questions about "{topic}" for {user_class} students.

Each question must have:
- Exactly 4 options (A, B, C, D)
- Exactly one correct answer
- Be appropriate for {user_class} level
- Be specific to the topic "{topic}"

Return ONLY valid JSON in this exact format:
{{
  "quiz": [
    {{
      "question": "What is the main concept in {topic}?",
      "options": ["Option A", "Option B", "Option C", "Option D"],
      "answer_index": 1
    }}
  ]
}}
Make sure all 10 questions are about {topic} and appropriate for {user_class} students."""
    try:
        try:
            response = requests.post(
                "http://localhost:11434/api/generate",
                json={"model": "llama3", "prompt": prompt, "stream": False},
                timeout=60
            )
            if response.status_code == 200:
                result = response.json()
                full_output = result.get("response", "")
                print(f"✅ Got response from Ollama HTTP API")
            else:
                raise Exception(f"Ollama HTTP API failed with status {response.status_code}")
        except Exception as e:
            print(f"⚠️ Ollama HTTP API failed: {e}, trying subprocess...")
            process = subprocess.Popen(
                ["ollama", "run", "llama3"],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )
            stdout, stderr = process.communicate(prompt, timeout=60)
            full_output = stdout.strip()
            print(f"✅ Got response from Ollama subprocess")

        # Clean and parse JSON (more robust extraction)
        output = re.sub(r"^\`\`\`json\s*|\s*\`\`\`$", "", full_output.strip(), flags=re.IGNORECASE)
        quiz_data = None
        try:
            parsed = json.loads(output)
            quiz_data = parsed if isinstance(parsed, dict) else {"quiz": parsed}
        except Exception:
            m = re.search(r"\{[\s\S]*\"quiz\"[\s\S]*\}", output)
            if m:
                quiz_data = json.loads(m.group(0))
        if not quiz_data or "quiz" not in quiz_data:
            raise ValueError("Invalid quiz format from model")

        # Enforce structure + uniqueness + shuffle options
        used_map = session.get("used_questions", {})
        used_set = set(used_map.get(topic, []))
        unique_quiz = _fill_unique_questions(quiz_data.get("quiz", []), topic, user_class, used_set)
        quiz_data = {"quiz": unique_quiz}
        print(f"✅ Generated {len(quiz_data['quiz'])} unique questions")
    except Exception as e:
        print(f"⚠️ JSON parsing failed or generation error: {e}, using fallback questions")
        quiz_data = create_fallback_quiz(topic, user_class)

    # Save new quiz, update cache and cross-generation dedupe
    save_quiz_to_db(user_name, topic, user_class, quiz_data)
    session["quiz_cache"] = {"topic": topic, "payload": quiz_data}
    _update_used_questions_session(topic, quiz_data["quiz"])
    return jsonify(quiz_data), 200

def create_fallback_quiz(topic, user_class):
    """
    Create a robust fallback quiz:
    - For math-like topics: generate 10 unique arithmetic questions with shuffled options.
    - For other topics: use safe templated questions (unique) and shuffle options.
    """
    topic_lower = (topic or "").lower()
    is_math = any(k in topic_lower for k in ["math", "algebra", "geometry", "arithmetic", "number", "fraction", "equation"])

    used_map = session.get("used_questions", {})
    used_set = set(used_map.get(topic, []))

    if is_math:
        questions = []
        # keep generating unique math questions until we have 10
        attempts = 0
        while len(questions) < 10 and attempts < 200:
            attempts += 1
            q = _gen_unique_math_question()
            qt = _normalize_text(q["question"])
            if qt not in used_set and all(_normalize_text(x["question"]) != qt for x in questions):
                questions.append(q)
    else:
        base = [
            {
                "question": f"Which statement is true about {topic}?",
                "options": ["It has real-world applications", "It is never used", "It has no practical value", "Only experts can learn it"],
                "answer_index": 0
            },
            {
                "question": f"Why is {topic} important for {user_class} students?",
                "options": ["It builds core understanding", "It is optional trivia", "It replaces all subjects", "It has no benefits"],
                "answer_index": 0
            },
            {
                "question": f"What is a common way to learn {topic}?",
                "options": ["Practice and examples", "Avoid studying", "Ignore feedback", "Memorize random facts"],
                "answer_index": 0
            },
            {
                "question": f"Which option best describes {topic}?",
                "options": ["A set of key concepts", "A single fixed rule", "A random idea", "A secret method"],
                "answer_index": 0
            },
            {
                "question": f"How can {topic} connect to daily life?",
                "options": ["Through practical examples", "It cannot", "Only in labs", "Only on exams"],
                "answer_index": 0
            },
            {
                "question": f"What helps mastery of {topic}?",
                "options": ["Regular practice", "Avoid mistakes", "Never review", "Skip feedback"],
                "answer_index": 0
            },
            {
                "question": f"What should {user_class} students focus on in {topic}?",
                "options": ["Core ideas and practice", "Only memorization", "Only shortcuts", "Only advanced tricks"],
                "answer_index": 0
            },
            {
                "question": f"What is a good first step to study {topic}?",
                "options": ["Understand basics", "Skip basics", "Only take tests", "Ignore examples"],
                "answer_index": 0
            },
            {
                "question": f"How can feedback improve {topic} learning?",
                "options": ["It corrects mistakes", "It blocks progress", "It confuses learners", "It replaces practice"],
                "answer_index": 0
            },
            {
                "question": f"Which resource best supports learning {topic}?",
                "options": ["Clear examples", "Random posts", "Unverified tips", "Unrelated content"],
                "answer_index": 0
            },
        ]
        # filter out any previously used question texts
        questions = []
        for q in base:
            if _normalize_text(q["question"]) not in used_set:
                questions.append(q)
        # ensure 10 questions (add harmless unique variants)
        idx = 1
        while len(questions) < 10:
            variant = {
                "question": f"Another helpful fact about {topic} ({idx})?",
                "options": ["It is easier with examples", "It cannot be learned", "Practice is harmful", "Only experts benefit"],
                "answer_index": 0
            }
            if _normalize_text(variant["question"]) not in used_set:
                questions.append(variant)
            idx += 1

    # shuffle options and finalize
    questions = [_shuffle_options_preserve_answer(q) for q in questions[:10]]
    payload = {"quiz": questions}
    print(f"✅ Fallback produced {len(payload['quiz'])} unique questions")
    return payload

@app.route("/submit_quiz", methods=["POST"])
def submit_quiz():
    data = request.get_json() or {}
    answers = data.get("answers", [])
    user_name = session.get("user_name", "User")
    topic = session.get("current_topic", "General Knowledge")

    quiz_cache = session.get("quiz_cache", {})
    quiz = quiz_cache.get("payload", {}).get("quiz", [])

    if not quiz:
        return jsonify({"error": "No quiz found. Please generate a quiz first."}), 400

    correct_count = 0
    details = []

    for i, q in enumerate(quiz):
        correct_idx = q.get("answer_index")
        user_idx = answers[i] if i < len(answers) else -1
        is_correct = user_idx == correct_idx

        if is_correct:
            correct_count += 1

        details.append({
            "question": q["question"],
            "correct": q["options"][correct_idx] if correct_idx is not None and correct_idx < len(q["options"]) else "N/A",
            "your_answer": q["options"][user_idx] if user_idx >= 0 and user_idx < len(q["options"]) else "No Answer",
            "is_correct": is_correct
        })

    percentage = (correct_count / len(quiz)) * 100
    save_quiz_to_db(user_name, topic, None, None, correct_count, len(quiz), percentage)

    # Award points for quiz completion
    username = session.get("username")
    if username and correct_count >= len(quiz) * 0.7:  # 70% or better
        award_points(username, "quiz_pass")
        check_and_award_badges(username)

    return jsonify({
        "score": correct_count,
        "total": len(quiz),
        "details": details
    })

# --- EVALUATE the student's short answer to the open-ended question ---
@app.route("/evaluate_paragraph", methods=["POST"])
def evaluate_paragraph():
    import re, json, subprocess
    data = request.json or {}
    user_text = data.get("text", "").strip()
    question = data.get("question", "").strip()
    topic = session.get("current_topic", "General Topic")

    prompt = f"""You are grading a student's short answer.

QUESTION:
{question}

STUDENT ANSWER:
{user_text}

TASK:
- Judge correctness and completeness vs the QUESTION (not just grammar)
- Briefly point out what is correct and what's missing/wrong
- Recommend up to 3 specific subtopics to review
- Give a score 0-10 (integer)
- You can give 0 and low scores as well    

Return ONLY JSON:
{{
  "score": 8,
  "correctness": "partially correct",  // one of: correct, partially correct, incorrect
  "feedback": "…concise feedback…",
  "weak_topics": ["…","…"]
}}"""

    process = subprocess.Popen(
        ["ollama", "run", "llama3"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    stdout, stderr = process.communicate(prompt.encode("utf-8"), timeout=45)
    output = stdout.decode("utf-8", errors="ignore").strip()
    output = re.sub(r"^\`\`\`json\s*|\s*\`\`\`$", "", output, flags=re.IGNORECASE).strip()

    try:
        result = json.loads(output)
    except Exception:
        m = re.search(r"\{.*\}", output, re.DOTALL)
        result = json.loads(m.group(0)) if m else {
            "score": 0, "correctness": "incorrect",
            "feedback": "Could not parse evaluation.", "weak_topics": []
        }

    # normalize fields
    result["score"] = int(result.get("score", 0))
    result["correctness"] = str(result.get("correctness", "partially correct")).lower()
    result["feedback"] = str(result.get("feedback", "")).strip()
    result["weak_topics"] = result.get("weak_topics") or []
    return jsonify(result), 200

    topic = session.get("current_topic", "General Topic")
    user_class = session.get("user_class", "high school")

    prompt = f"""
    You are an educational quiz generator.
    Create exactly 10 multiple-choice questions for {user_class} students about "{topic}".
    Each question should have 4 options (A, B, C, D) with one correct answer.
    Return ONLY JSON, no explanations, in this format:
    [
      {{
        "question": "What is ...?",
        "options": ["Option A", "Option B", "Option C", "Option D"],
        "answer": "A"
      }},
      ...
    ]
    """

    process = subprocess.Popen(
        ["ollama", "run", "llama3"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    stdout, stderr = process.communicate(prompt.encode("utf-8"), timeout=60)
    output = stdout.decode("utf-8", errors="ignore").strip()

    import re, json
    output = re.sub(r"^\`\`\`json", "", output).strip()
    output = re.sub(r"\`\`\`$", "", output).strip()

    try:
        quiz_data = json.loads(output)
    except:
        match = re.search(r"\[.*\]", output, re.DOTALL)
        quiz_data = json.loads(match.group(0)) if match else []

    return jsonify({"quiz": quiz_data}), 200

# -------------------- VIDEO GENERATION --------------------

@app.route("/get_generation_progress", methods=["POST"])
def get_generation_progress():
    """Get real-time progress of video generation"""
    topic = session.get("current_topic", "General Topic")
    interests = session.get("user_interests", "science")
    interest_hash = get_interest_hash(interests.split(","))
    folder_name = f"{topic.replace(' ', '_')}__{interest_hash}"
    
    progress_data = video_generation_progress.get(folder_name, {
        'progress': 0,
        'step': 0,
        'message': 'Initializing...',
        'status': 'processing'
    })
    
    return jsonify(progress_data)

@app.route("/generate_video", methods=["POST"])
def generate_video_route():
    topic = session.get("current_topic", "General Topic")
    interests = session.get("user_interests", "science")
    user_class = session.get("user_class", "high school")
    
    try:
        # Start video generation in background thread with user data
        thread = threading.Thread(target=generate_video_async, args=(topic, interests, user_class))
        thread.daemon = True
        thread.start()
        
        interest_hash = get_interest_hash(interests.split(","))
        folder_name = f"{topic.replace(' ', '_')}__{interest_hash}"
        
        return jsonify({
            "status": "processing",
            "message": "Video generation started",
            "folder": folder_name
        })
    except Exception as e:
        print(f"❌ Video generation route error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/regenerate_video", methods=["POST"])
def regenerate_video_route():
    topic = session.get("current_topic", "General Topic")
    interests = session.get("user_interests", "science")
    user_class = session.get("user_class", "high school")
    
    try:
        interest_hash = get_interest_hash(interests.split(","))
        folder_name = f"{topic.replace(' ', '_')}__{interest_hash}"
        base_dir = os.path.join(app.root_path, "static", "generated_videos", folder_name)
        
        # Delete existing video files to force regeneration
        files_to_delete = [
            "final_output_video.mp4",
            "output_video.mp4",
            "output.wav",
            "script.txt",
            "captions.srt",
            "image_prompts.txt"
        ]
        
        for file_name in files_to_delete:
            file_path = os.path.join(base_dir, file_name)
            if os.path.exists(file_path):
                os.remove(file_path)
                print(f"🗑️ Deleted: {file_name}")
        
        # Also delete generated images folder
        images_dir = os.path.join(base_dir, "generated_images")
        if os.path.exists(images_dir):
            import shutil
            shutil.rmtree(images_dir)
            print("🗑️ Deleted generated images folder")
        
        # Start video generation in background thread with user data
        thread = threading.Thread(target=generate_video_async, args=(topic, interests, user_class))
        thread.daemon = True
        thread.start()
        
        return jsonify({
            "status": "processing",
            "message": "Video regeneration started",
            "folder": folder_name
        })
    except Exception as e:
        print(f"❌ Video regeneration error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/check_video_status", methods=["POST"])
def check_video_status():
    topic = session.get("current_topic", "General Topic")
    interests = session.get("user_interests", "science")
    interest_hash = get_interest_hash(interests.split(","))
    folder_name = f"{topic.replace(' ', '_')}__{interest_hash}"
    
    video_path = os.path.join(app.root_path, "static", "generated_videos", folder_name, "final_output_video.mp4")
    
    if os.path.exists(video_path):
        # Get file modification time to check if it's newly generated
        file_time = os.path.getmtime(video_path)
        current_time = time.time()
        is_recent = (current_time - file_time) < 300  # Within last 5 minutes
        
        return jsonify({
            "status": "completed",
            "video_url": f"/static/generated_videos/{folder_name}/final_output_video.mp4",
            "is_recent": is_recent
        })
    else:
        return jsonify({"status": "processing"})

def update_progress(folder_name, progress, step, message, substep=None):
    """Update progress for a specific video generation"""
    video_generation_progress[folder_name] = {
        'progress': progress,
        'step': step,
        'message': message,
        'substep': substep,
        'status': 'processing'
    }
    print(f"📊 Progress: {progress}% - {message}")

def complete_progress(folder_name, video_url):
    """Mark video generation as completed"""
    video_generation_progress[folder_name] = {
        'progress': 100,
        'step': 6,
        'message': 'Video generation completed!',
        'status': 'completed',
        'video_url': video_url
    }

def generate_video_async(topic, interests, user_class):
    """Generate video asynchronously with proper error handling"""
    try:
        print(f"🎬 Starting video generation for topic: {topic}, interests: {interests}, class: {user_class}")
        
        interest_hash = get_interest_hash(interests.split(","))
        folder_name = f"{topic.replace(' ', '_')}__{interest_hash}"
        base_dir = os.path.join(app.root_path, "static", "generated_videos", folder_name)
        final_output = os.path.join(base_dir, "final_output_video.mp4")
        
        # Create directory if it doesn't exist
        os.makedirs(base_dir, exist_ok=True)
        print(f"📁 Created directory: {base_dir}")
        
        # Generate video using the advanced pipeline
        success = generate_educational_video(topic, interests, user_class, base_dir, folder_name)
        
        if success and os.path.exists(final_output):
            print(f"✅ Video generation completed successfully: {final_output}")
            video_url = f"/static/generated_videos/{folder_name}/final_output_video.mp4"
            complete_progress(folder_name, video_url)
        else:
            print(f"❌ Video generation failed - no output file created")
            video_generation_progress[folder_name] = {
                'progress': 0,
                'step': 0,
                'message': 'Video generation failed',
                'status': 'error'
            }
        
    except Exception as e:
        print(f"❌ Video generation failed with error: {e}")
        import traceback
        traceback.print_exc()
        
        # Update progress with error
        interest_hash = get_interest_hash(interests.split(","))
        folder_name = f"{topic.replace(' ', '_')}__{interest_hash}"
        video_generation_progress[folder_name] = {
            'progress': 0,
            'step': 0,
            'message': f'Error: {str(e)}',
            'status': 'error'
        }

def generate_educational_video(topic, interests, user_class, base_dir, folder_name):
    """Complete video generation function with class-based content and progress tracking"""
    try:
        print(f"🎬 Starting educational video generation for {user_class} level...")
        
        output_images_dir = os.path.join(base_dir, "generated_images")
        os.makedirs(output_images_dir, exist_ok=True)
        
        prompts_file = os.path.join(base_dir, "image_prompts.txt")
        audio_script_file = os.path.join(base_dir, "script.txt")
        captions_file = os.path.join(base_dir, "captions.srt")
        audio_file = os.path.join(base_dir, "output.wav")
        video_file = os.path.join(base_dir, "output_video.mp4")
        final_output = os.path.join(base_dir, "final_output_video.mp4")
        
        # Step 1: Generate image prompts (5% progress)
        update_progress(folder_name, 5, 0, "Generating educational image prompts...")
        image_prompts = generate_image_prompts_with_class(topic, interests, user_class)
        print(f"✅ Generated {len(image_prompts)} image prompts for {user_class} level")
        
        with open(prompts_file, "w", encoding="utf-8") as f:
            for i, prompt in enumerate(image_prompts, 1):
                f.write(f"{i}. {prompt}\n")
        
        # Step 2: Generate images using Stable Diffusion (5% to 60% progress)
        update_progress(folder_name, 10, 1, "Starting AI image generation...")
        if not generate_educational_images_with_progress(output_images_dir, topic, image_prompts, folder_name):
            print("❌ Image generation failed - cannot create video without images")
            return False
        
        # Step 3: Generate narration script based on images and class (65% progress)
        update_progress(folder_name, 65, 2, "Analyzing images and creating narration script...")
        voice_lines = generate_voice_script_with_class(topic, interests, user_class, output_images_dir)
        if not voice_lines:
            print("❌ Script generation failed")
            return False
        
        print(f"✅ Generated {len(voice_lines)} voice lines for {user_class} level")
        
        full_script = " ".join(voice_lines)
        with open(audio_script_file, "w", encoding="utf-8") as f:
            f.write(full_script)
        
        # Step 4: Generate audio (75% progress)
        update_progress(folder_name, 75, 3, "Creating professional voiceover...")
        if not generate_audio_advanced(full_script, audio_file):
            print("❌ Audio generation failed")
            return False
        
        # Step 5: Get audio duration and create video (85% progress)
        update_progress(folder_name, 85, 4, "Building video with transitions and captions...")
        try:
            if os.path.exists(audio_file):
                # Try to get audio duration
                try:
                    import librosa
                    audio_duration = librosa.get_duration(path=audio_file)
                    print(f"🎵 Audio duration: {audio_duration:.2f} seconds")
                except ImportError:
                    # Fallback duration calculation
                    audio_duration = len(full_script.split()) / 150 * 60
                    print(f"🎵 Estimated audio duration: {audio_duration:.2f} seconds")
            else:
                audio_duration = len(full_script.split()) / 150 * 60
                print(f"🎵 Estimated audio duration: {audio_duration:.2f} seconds")
        except Exception as e:
            print(f"⚠️ Could not get audio duration: {e}")
            audio_duration = len(full_script.split()) / 150 * 60
        
        # Generate synchronized captions
        sentence_timings = estimate_sentence_timing_advanced(voice_lines, audio_duration)
        create_synced_srt_file(voice_lines, sentence_timings, captions_file)
        
        # Create video with transitions and captions
        if not create_video_with_advanced_transitions(output_images_dir, video_file, sentence_timings, voice_lines, audio_duration):
            print("❌ Video creation failed")
            return False
        
        # Step 6: Combine with audio (95% progress)
        update_progress(folder_name, 95, 5, "Adding audio and finalizing video...")
        if not combine_audio_video_advanced(video_file, audio_file, final_output):
            print("❌ Audio-video combination failed")
            return False
        
        # Complete (100% progress)
        video_url = f"/static/generated_videos/{folder_name}/final_output_video.mp4"
        complete_progress(folder_name, video_url)
        
        print("🎉 Video generation completed!")
        return True
        
    except Exception as e:
        print(f"❌ Error in generate_educational_video: {e}")
        import traceback
        traceback.print_exc()
        return False
def generate_educational_images_with_progress(output_dir, topic, prompts, folder_name):
    """Generate images with detailed progress tracking using Stable Diffusion"""
    print("🎨 Generating images with Stable Diffusion and progress tracking...")

    try:
        # Check for required libraries
        try:
            from diffusers import StableDiffusionPipeline
            import torch
            import cv2
        except ImportError as e:
            print(f"❌ Required libraries not installed: {e}")
            print("👉 Please install: pip install diffusers torch transformers accelerate opencv-python")
            return False

        # Detect device and dtype
        device = "cuda" if torch.cuda.is_available() else "cpu"
        dtype = torch.float16 if device == "cuda" else torch.float32

        update_progress(folder_name, 15, 1, "Loading AI image generation model...", "Initializing Stable Diffusion")

        try:
            # ✅ FIXED: No device_map="auto" (avoids meta tensor issue)
            pipe = StableDiffusionPipeline.from_pretrained(
                "runwayml/stable-diffusion-v1-5",
                torch_dtype=dtype,
                safety_checker=None
            )

            pipe = pipe.to(device)

            # Reduce VRAM usage if on GPU
            if device == "cuda":
                pipe.enable_attention_slicing()
                # pipe.enable_vae_slicing()
                # pipe.enable_sequential_cpu_offload()

            print(f"🎨 Using device: {device}, dtype: {dtype}")

        except Exception as e:
            import traceback
            print("❌ Failed to load Stable Diffusion model:")
            traceback.print_exc()
            return False

        # Generate images with progress updates
        total_images = len(prompts)
        for idx, prompt in enumerate(prompts):
            current_progress = 20 + int((idx / total_images) * 40)  # 20% → 60%
            update_progress(folder_name, current_progress, 1, "Generating educational images...", f"Image {idx+1}/{total_images}")

            try:
                enhanced_prompt = (
                    f"{prompt}, educational illustration, professional, detailed, "
                    f"high quality, 16:9 aspect ratio, clean background"
                )

                image = pipe(
                    enhanced_prompt,
                    num_inference_steps=25,
                    guidance_scale=7.5,
                    width=768,
                    height=432,
                    negative_prompt="blurry, low quality, distorted, ugly, bad anatomy, text, watermark, signature"
                ).images[0]

                # Convert to proper 16:9 format
                image_16_9 = resize_to_16_9_advanced(image)

                # Save with high quality
                output_path = os.path.join(output_dir, f"image_{idx+1:02d}.png")
                cv2.imwrite(output_path, cv2.cvtColor(image_16_9, cv2.COLOR_RGB2BGR))

                print(f"✅ Generated educational image {idx+1}/{total_images}")

            except Exception as e:
                import traceback
                print(f"⚠️ Failed to generate image {idx+1}: {e}")
                traceback.print_exc()
                # Create fallback placeholder
                create_fallback_image(output_dir, idx+1, prompt, topic)

        # Clear GPU memory
        if device == "cuda":
            torch.cuda.empty_cache()

        update_progress(folder_name, 60, 1, "All images generated successfully!", "Completed")
        print(f"✅ Successfully generated all {total_images} images")
        return True

    except Exception as e:
        import traceback
        print("❌ Stable Diffusion setup failed:")
        traceback.print_exc()
        # Create fallback images
        print("🎨 Creating fallback placeholder images...")
        for idx, prompt in enumerate(prompts):
            create_fallback_image(output_dir, idx+1, prompt, topic)
        return False


def create_fallback_image(output_dir, idx, prompt, topic):
    """Create a fallback placeholder image when AI generation fails"""
    try:
        import cv2
        
        # Create image
        img = np.ones((VIDEO_HEIGHT, VIDEO_WIDTH, 3), dtype=np.uint8) * 245
        
        # Add gradient background
        for i in range(VIDEO_HEIGHT):
            intensity = int(245 - (i / VIDEO_HEIGHT) * 30)
            img[i, :] = [intensity, intensity + 5, intensity + 10]
        
        # Add border
        cv2.rectangle(img, (20, 20), (VIDEO_WIDTH-20, VIDEO_HEIGHT-20), (200, 200, 200), 3)
        
        # Add title
        cv2.putText(img, f"Learning {topic}", (50, 100), cv2.FONT_HERSHEY_SIMPLEX, 2, (50, 50, 50), 3)
        
        # Add scene number
        cv2.putText(img, f"Scene {idx}", (50, 200), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (80, 80, 80), 2)
        
        # Add wrapped prompt text
        words = prompt.split()[:8]
        text_line = " ".join(words)
        if len(text_line) > 40:
            text_line = text_line[:40] + "..."
        
        cv2.putText(img, text_line, (50, VIDEO_HEIGHT//2), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (80, 80, 80), 2)
        
        # Add educational icon
        cv2.putText(img, "📚", (VIDEO_WIDTH-150, VIDEO_HEIGHT-50), cv2.FONT_HERSHEY_SIMPLEX, 2, (100, 100, 100), 3)
        
        # Save image
        output_path = os.path.join(output_dir, f"image_{idx:02d}.png")
        cv2.imwrite(output_path, img)
        
    except Exception as e:
        print(f"❌ Failed to create fallback image: {e}")

def resize_to_16_9_advanced(image, target_width=VIDEO_WIDTH, target_height=VIDEO_HEIGHT):
    """Advanced resize with better quality preservation for 16:9 aspect ratio"""
    import cv2
    
    # Convert PIL Image to numpy array if needed
    if hasattr(image, 'convert'):
        img_array = np.array(image.convert('RGB'))
    else:
        img_array = np.array(image)
    
    h, w = img_array.shape[:2]
    
    # Calculate scaling to fit within target dimensions while maintaining aspect ratio
    scale = min(target_width/w, target_height/h)
    new_w = int(w * scale)
    new_h = int(h * scale)
    
    # Use high-quality interpolation
    resized = cv2.resize(img_array, (new_w, new_h), interpolation=cv2.INTER_LANCZOS4)
    
    # Create canvas with gradient background
    canvas = np.zeros((target_height, target_width, 3), dtype=np.uint8)
    
    # Add subtle gradient background
    for i in range(target_height):
        intensity = int(240 - (i / target_height) * 20)
        canvas[i, :] = [intensity, intensity, intensity]
    
    # Center the resized image on canvas
    y_offset = (target_height - new_h) // 2
    x_offset = (target_width - new_w) // 2
    canvas[y_offset:y_offset+new_h, x_offset:x_offset+new_w] = resized
    
    return canvas

def generate_image_prompts_with_class(topic, interests, user_class):
    """Generate image prompts appropriate for the student's class level"""
    print(f"🧠 Generating prompts for {user_class} level: {topic}, interests: {interests}")
    
    # Create class-appropriate prompt
    class_context = {
        "elementary": "simple, basic concepts, colorful, fun illustrations suitable for young students",
        "middle school": "clear explanations, engaging visuals, age-appropriate complexity for middle school students", 
        "high school": "detailed concepts, academic illustrations, appropriate complexity for high school level",
        "college": "advanced concepts, technical diagrams, university-level complexity and detail",
        "graduate": "sophisticated analysis, research-level illustrations, advanced academic content"
    }
    
    class_level = class_context.get(user_class.lower(), class_context["high school"])
    
    ollama_prompt = f"""Generate 15 detailed image prompts for an educational video about "{topic}" for {user_class} students interested in {interests}.
Make the content appropriate for {user_class} level with {class_level}.
Each prompt should describe a specific educational scene that will be used to generate an AI image. Make each prompt:
- Appropriate for {user_class} level understanding
- Highly detailed and specific to {topic}
- Educational and informative for {user_class} students
- Visually engaging and clear
- Suitable for AI image generation
- Progressive (building from basic to advanced concepts appropriate for {user_class})
- Connected to {interests} when relevant

Write exactly 15 image prompts, one per line:
1.
2.
3.
..."""

    try:
        process = subprocess.Popen(
            ['ollama', 'run', 'llama3'],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding='utf-8',
            errors='replace'
        )
        stdout, stderr = process.communicate(ollama_prompt, timeout=120)
        
        if process.returncode == 0:
            lines = clean_ollama_response(stdout)
            prompts = []
            for line in lines[:15]:
                if line.strip() and len(line.split()) > 5:
                    prompts.append(line.strip())
            
            while len(prompts) < 15:
                prompts.append(f"Educational diagram showing {topic} concept {len(prompts)+1} for {user_class} students")
            
            print(f"✅ Generated {len(prompts)} class-appropriate prompts")
            return prompts[:15]
            
    except Exception as e:
        print(f"⚠️ Ollama prompt generation failed: {e}")
    
    # Enhanced fallback prompts with class level
    base_prompts = [
        f"Educational diagram explaining {topic} fundamentals for {user_class} students",
        f"Step-by-step visual guide showing {topic} concepts appropriate for {user_class} level",
        f"Professional infographic displaying {topic} key ideas for {user_class} students",
        f"Clear illustration demonstrating {topic} principles at {user_class} level",
        f"Educational chart showing {topic} important concepts for {user_class} students",
        f"Visual diagram of {topic} essential elements appropriate for {user_class}",
        f"Instructional graphic explaining {topic} for {user_class} level understanding",
        f"Academic illustration of {topic} concepts suitable for {user_class} students",
        f"Educational flowchart showing {topic} processes for {user_class} level",
        f"Clear diagram displaying {topic} applications for {user_class} students",
        f"Visual representation of {topic} principles appropriate for {user_class}",
        f"Educational poster design explaining {topic} for {user_class} level",
        f"Instructional diagram showing {topic} concepts for {user_class} students",
        f"Academic visualization of {topic} ideas suitable for {user_class} level",
        f"Educational schematic explaining {topic} for {user_class} understanding"
    ]
    
    print(f"✅ Using class-appropriate fallback prompts for {user_class}")
    return base_prompts
def generate_narration_scripts(topic, level, num_scenes=15):
    """
    Generate clean narration lines for each scene (no meta text).
    """
    print(f"🗣️ Generating {level}-level voice script for topic: {topic}")

    # Example fallback narration lines (when GPT fails or times out)
    fallback_lines = [
        f"Welcome to our lesson on {topic}.",
        f"This is an important part of {topic}.",
        f"Let’s explore how {topic} shaped history.",
        f"Notice how {topic} connects with daily life.",
        f"This is a key idea in {topic}.",
        f"Now let’s look deeper into {topic}.",
        f"This picture shows an example of {topic}.",
        f"As you can see, {topic} is very important.",
        f"Here’s another interesting fact about {topic}.",
        f"This will help you understand {topic} better.",
        f"Think about how {topic} affects the world.",
        f"Let’s summarize the main idea of {topic}.",
        f"This scene shows {topic} in action.",
        f"Learning {topic} helps us grow smarter.",
        f"Thank you for exploring {topic} with us!"
    ]

    # Trim to number of scenes
    return fallback_lines[:num_scenes]
def clean_script(raw_text):
    """
    Remove unwanted phrases like 'Here are...' or 'Scene 1:'
    """
    lines = raw_text.splitlines()
    cleaned = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if line.lower().startswith("here are"):
            continue
        if line.lower().startswith("scene"):
            # Keep only text after colon
            if ":" in line:
                line = line.split(":", 1)[-1].strip()
        cleaned.append(line)
    return cleaned

def generate_voice_script_with_class(topic, interests, user_class, images_dir):
    """Generate voice script appropriate for the student's class level"""
    print(f"🗣️ Generating {user_class}-level voice script for topic: {topic}")
    
    images = sorted([img for img in os.listdir(images_dir) if img.endswith(".png")])
    if not images:
        print("❌ No images found to generate script from!")
        return []
    
    print(f"📸 Found {len(images)} images to analyze for {user_class} level")
    
    # Class-appropriate language and complexity
    class_instructions = {
        "elementary": "Use simple words, short sentences, and exciting language that young students can easily understand. Make it fun and engaging.",
        "middle school": "Use clear explanations with moderate vocabulary. Include interesting facts and relatable examples for middle school students.",
        "high school": "Use academic language appropriate for high school level. Include detailed explanations and real-world applications.",
        "college": "Use sophisticated vocabulary and complex concepts appropriate for university students. Include technical details and advanced applications.",
        "graduate": "Use advanced academic language and complex theoretical concepts appropriate for graduate-level study."
    }
    
    class_instruction = class_instructions.get(user_class.lower(), class_instructions["high school"])
    
    ollama_prompt = f"""You are creating a detailed educational narration script for a video about "{topic}" for {user_class} students interested in {interests}.
{class_instruction}
The video has {len(images)} educational scenes/images that will be shown in sequence. 

Create exactly {len(images)} narration sentences - one for each scene. Each sentence should:
- Be appropriate for {user_class} level understanding
- Be 12-18 words long for clear narration
- Build upon the previous sentence to create a flowing educational story
- Be specific to the topic "{topic}"
- Connect to student interests in {interests}
- Explain concepts progressively from basic to advanced (appropriate for {user_class})
- Use engaging, educational language suitable for {user_class} students

Write exactly {len(images)} sentences, one per line, that will narrate this educational video about {topic} for {user_class} students:
1.
2.
3.
..."""

    try:
        process = subprocess.Popen(
            ['ollama', 'run', 'llama3'],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding='utf-8',
            errors='replace'
        )
        stdout, stderr = process.communicate(ollama_prompt, timeout=120)
        
        if process.returncode == 0:
            lines = clean_ollama_response(stdout)
            voice_lines = []
            
            for line in lines:
                cleaned_line = line.strip()
                if cleaned_line and len(cleaned_line.split()) >= 8:
                    voice_lines.append(cleaned_line)
            
            while len(voice_lines) < len(images):
                voice_lines.append(f"This concept helps {user_class} students understand another important aspect of {topic}.")
            
            voice_lines = voice_lines[:len(images)]
            
            print(f"✅ Generated {len(voice_lines)} class-appropriate voice lines")
            return voice_lines
            
    except Exception as e:
        print(f"⚠️ Ollama script generation failed: {e}")
    
    # Class-appropriate fallback script
    print(f"📝 Creating {user_class}-level educational script as fallback...")
    basic_script = []
    for i in range(len(images)):
        if i == 0:
            basic_script.append(f"Welcome to our {user_class}-level exploration of {topic} and its important concepts.")
        elif i == 1:
            basic_script.append(f"Let's understand the fundamental principles of {topic} at the {user_class} level.")
        elif i == len(images) - 1:
            basic_script.append(f"This completes our {user_class}-level journey through {topic} and its applications.")
        else:
            basic_script.append(f"This {user_class}-level concept reveals another important aspect of {topic}.")
    
    return basic_script

def create_synced_srt_file(voice_lines, sentence_timings, output_file):
    """Create properly formatted SRT subtitle file"""
    try:
        with open(output_file, "w", encoding="utf-8") as f:
            for i, (line, timing) in enumerate(zip(voice_lines, sentence_timings)):
                def format_srt_time(seconds):
                    seconds = max(0, seconds)
                    hours = int(seconds // 3600)
                    minutes = int((seconds % 3600) // 60)
                    secs = int(seconds % 60)
                    millisecs = int((seconds % 1) * 1000)
                    
                    hours = min(23, max(0, hours))
                    minutes = min(59, max(0, minutes))
                    secs = min(59, max(0, secs))
                    millisecs = min(999, max(0, millisecs))
                    
                    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millisecs:03d}"
                
                f.write(f"{i+1}\n")
                f.write(f"{format_srt_time(timing['start'])} --> {format_srt_time(timing['end'])}\n")
                f.write(f"{line.strip()}\n\n")
        
        print(f"✅ SRT caption file created: {output_file}")
            
    except Exception as e:
        print(f"❌ Failed to create SRT file: {e}")

def create_video_with_advanced_transitions(images_dir, video_file, sentence_timings, voice_lines, audio_duration):
    """Create video with transitions and captions"""
    try:
        import cv2
        
        print("🎬 Creating video with transitions...")
        
        # Get all generated images
        images = sorted([img for img in os.listdir(images_dir) if img.endswith(".png")])
        if not images:
            print("❌ No images found!")
            return False
        
        print(f"📸 Found {len(images)} images")
        
        # Load all images
        loaded_images = []
        for img_name in images[:15]:
            img_path = os.path.join(images_dir, img_name)
            frame = cv2.imread(img_path)
            if frame is None:
                print(f"⚠️ Could not load image: {img_name}")
                continue
            
            # Ensure frame is correct size
            if frame.shape[:2] != (VIDEO_HEIGHT, VIDEO_WIDTH):
                frame = cv2.resize(frame, (VIDEO_WIDTH, VIDEO_HEIGHT))
            
            loaded_images.append(frame)
        
        if len(loaded_images) < 1:
            print("❌ No valid images loaded!")
            return False
        
        print(f"✅ Loaded {len(loaded_images)} images")
        
        # Calculate timing
        num_images = len(loaded_images)
        image_display_time = audio_duration / num_images
        image_frames = max(int(image_display_time * TRANSITION_FPS), 24)  # At least 1 second per image
        
        print(f"📊 Video timing: {image_display_time:.2f}s per image ({image_frames} frames)")
        
        # Create video writer
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        video_writer = cv2.VideoWriter(video_file, fourcc, TRANSITION_FPS, (VIDEO_WIDTH, VIDEO_HEIGHT))
        
        if not video_writer.isOpened():
            print("❌ Could not open video writer!")
            return False
        
        print("🎬 Writing video frames...")
        current_video_time = 0
        frame_duration = 1.0 / TRANSITION_FPS
        
        for i, current_image in enumerate(loaded_images):
            print(f"   Processing image {i+1}/{len(loaded_images)}")
            
            # Display current image with captions
            for frame_idx in range(image_frames):
                # Get appropriate caption for current time
                caption = get_current_caption(current_video_time, sentence_timings, voice_lines)
                frame_with_caption = add_caption_to_frame_advanced(current_image.copy(), caption)
                video_writer.write(frame_with_caption)
                current_video_time += frame_duration
        
        video_writer.release()
        print(f"✅ Video created: {video_file}")
        return True
        
    except Exception as e:
        print(f"❌ Error creating video: {e}")
        import traceback
        traceback.print_exc()
        return False

def add_caption_to_frame_advanced(frame, caption_text, font_scale=0.9, thickness=2):
    """Add professional captions to frame"""
    import cv2
    
    if not caption_text:
        return frame
        
    # Wrap text to fit frame width
    max_chars_per_line = 55
    wrapped_lines = textwrap.wrap(caption_text, width=max_chars_per_line)
    
    # Calculate text dimensions
    font = cv2.FONT_HERSHEY_SIMPLEX
    line_height = 40
    padding = 25
    
    # Create semi-transparent background for text
    overlay = frame.copy()
    total_text_height = len(wrapped_lines) * line_height + (padding * 2)
    
    # Create background
    bg_start_y = max(0, VIDEO_HEIGHT - total_text_height - 10)
    bg_end_y = VIDEO_HEIGHT - 10
    
    # Draw background
    for i in range(bg_start_y, bg_end_y):
        overlay[i, :] = [20, 20, 20]
    
    # Blend overlay with original frame
    alpha = 0.85
    frame = cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0)
    
    # Add text lines
    for i, line in enumerate(wrapped_lines):
        # Calculate text size for centering
        (text_width, text_height), _ = cv2.getTextSize(line, font, font_scale, thickness)
        x = (VIDEO_WIDTH - text_width) // 2
        y = bg_start_y + padding + 30 + (i * line_height)
        
        # Add shadow
        cv2.putText(frame, line, (x+3, y+3), font, font_scale, (0, 0, 0), thickness+1)
        # Add main text
        cv2.putText(frame, line, (x, y), font, font_scale, (255, 255, 255), thickness)
    
    return frame

def get_current_caption(current_time, sentence_timings, voice_lines):
    """Get the appropriate caption for the current time"""
    for i, timing in enumerate(sentence_timings):
        if timing['start'] <= current_time <= timing['end']:
            return voice_lines[i] if i < len(voice_lines) else ""
    return ""

def estimate_sentence_timing_advanced(sentences, total_duration):
    """Advanced sentence timing with natural speech patterns"""
    word_counts = [len(sentence.split()) for sentence in sentences]
    total_words = sum(word_counts)
    
    # More realistic speaking rate
    speaking_rate = max(total_words / total_duration, 2.0)
    
    sentence_timings = []
    current_time = 0
    
    for i, word_count in enumerate(word_counts):
        # Base duration from word count
        base_duration = word_count / speaking_rate
        
        # Add natural pauses
        pause_duration = 0.4 if i < len(word_counts) - 1 else 0.1
        sentence_duration = base_duration + pause_duration
        
        sentence_timings.append({
            'start': current_time,
            'end': current_time + base_duration,
            'duration': sentence_duration
        })
        
        current_time += sentence_duration
    
    return sentence_timings

def generate_audio_advanced(script, audio_file):
    """Generate audio with multiple fallbacks (Edge-TTS → pyttsx3 → silent audio)."""
    print(f"🎧 Generating audio for script: {script[:100]}...")

    voices = ["en-US-AriaNeural", "en-GB-SoniaNeural", "en-IN-NeerjaNeural"]  # fallback voices

    # --- Try Edge-TTS voices ---
    for voice in voices:
        edge_command = [
            r"C:\Users\HP\AppData\Roaming\Python\Python310\Scripts\edge-tts.exe",
            "--voice", voice,
            "--rate", "+5%",
            "--pitch", "+2Hz",
            "--text", script,
            "--write-media", audio_file
        ]
        try:
            result = subprocess.run(
                edge_command, timeout=180, check=True,
                capture_output=True, text=True
            )
            print(f"✅ High-quality audio generated with {voice}")
            return True
        except Exception as e:
            print(f"⚠️ Edge-TTS failed with {voice}: {e}")
            continue

    # --- Fallback: pyttsx3 (offline) ---
    try:
        import pyttsx3
        engine = pyttsx3.init()
        engine.setProperty("rate", 175)   # speaking speed
        engine.setProperty("volume", 1.0) # full volume
        engine.save_to_file(script, audio_file)
        engine.runAndWait()
        print("✅ Audio generated with pyttsx3 (offline)")
        return True
    except Exception as e:
        print(f"⚠️ pyttsx3 failed: {e}")

    # --- Last fallback: silent audio ---
    try:
        duration = len(script.split()) / 150 * 60  # estimate in seconds
        sample_rate = 22050
        samples = int(duration * sample_rate)

        import wave
        with wave.open(audio_file, 'w') as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            silent_data = np.zeros(samples, dtype=np.int16)
            wav_file.writeframes(silent_data.tobytes())
        print("✅ Created silent audio fallback")
        return True
    except Exception as e:
        print(f"❌ Could not create audio file at all: {e}")
        return False

    """Generate audio with multiple fallbacks (Edge-TTS → pyttsx3 → silent audio)."""
    print(f"🎧 Generating audio for script: {script[:100]}...")

    temp_script = audio_file.replace('.wav', '_temp.txt')
    with open(temp_script, "w", encoding="utf-8") as f:
        f.write(script)

    # --- Try Edge-TTS first ---
    edge_command = [
        r"C:\Users\HP\AppData\Roaming\Python\Python310\Scripts\edge-tts.exe",
        "--voice", voice,
        "--rate", "+5%",
        "--pitch", "+2Hz",
        "--text", script,
        "--write-media", audio_file
    ]

    try:
        result = subprocess.run(
            edge_command, timeout=180, check=True,
            capture_output=True, text=True
        )
        if os.path.exists(temp_script):
            os.remove(temp_script)
        print("✅ High-quality audio generated with Edge-TTS")
        return True
    except Exception as e:
        print(f"⚠️ Edge-TTS failed: {e}")

    # --- Fallback: pyttsx3 (offline TTS) ---
    try:
        import pyttsx3
        engine = pyttsx3.init()
        engine.setProperty("rate", 175)   # adjust speaking rate
        engine.setProperty("volume", 1.0) # full volume
        engine.save_to_file(script, audio_file)
        engine.runAndWait()
        print("✅ Audio generated with pyttsx3 (offline)")
        return True
    except Exception as e:
        print(f"⚠️ pyttsx3 failed: {e}")

    # --- Last fallback: create silent audio ---
    try:
        duration = len(script.split()) / 150 * 60  # rough estimate
        sample_rate = 22050
        samples = int(duration * sample_rate)

        import wave
        with wave.open(audio_file, 'w') as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            silent_data = np.zeros(samples, dtype=np.int16)
            wav_file.writeframes(silent_data.tobytes())
        print("✅ Created silent audio fallback")
        return True
    except Exception as e:
        print(f"❌ Could not create audio file at all: {e}")
        return False

def combine_audio_video_advanced(video_file, audio_file, output_file):
    """Combine audio and video with normalization"""
    print(f"📽️ Combining {video_file} with {audio_file}")
    
    if not os.path.exists(video_file):
        print(f"❌ Video file not found: {video_file}")
        return False
    
    if not os.path.exists(audio_file):
        print(f"⚠️ Audio file not found, copying video only")
        import shutil
        shutil.copy2(video_file, output_file)
        return True
    
    ffmpeg_command = [
        "ffmpeg", "-y",
        "-i", video_file,
        "-i", audio_file,
        "-c:v", "libx264",        # standard video codec
        "-preset", "fast",
        "-crf", "23",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",            # force AAC audio
        "-b:a", "192k",           # good audio quality
        "-ar", "44100",           # normalize sample rate
        "-ac", "2",               # stereo output
        "-shortest",              # cut extra video or audio
        output_file
    ]
    
    try:        
        result = subprocess.run(
            ffmpeg_command, 
            timeout=600,
            check=True,
            capture_output=True,
            text=True
        )
        print("✅ High-quality final video with audio created")
        return True
    except Exception as e:
        print(f"⚠️ FFmpeg failed: {e}")
        # Fallback: just copy video
        import shutil
        shutil.copy2(video_file, output_file)
        print("✅ Copied video as fallback (no audio)")
        return True

def clean_ollama_response(text):
    """Clean up Ollama response"""
    lines = text.strip().split('\n')
    cleaned_lines = []
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        line = re.sub(r'^\d+\.\s*', '', line)
        line = re.sub(r'^[-*]\s*', '', line)
        
        if len(line.split()) > 5 and len(line) > 20:
            cleaned_lines.append(line)
    
    return cleaned_lines

    """Clean up Ollama response"""
    lines = text.strip().split('\n')
    cleaned_lines = []

    for line in lines:
        line = line.strip()
        if not line:
            continue

        line = re.sub(r'^\d+\.\s*', '', line)
        line = re.sub(r'^[-*]\s*', '', line)

        if len(line.split()) > 5 and len(line) > 20:
            cleaned_lines.append(line)

    return cleaned_lines

# -------------------- AUDIO NOTES --------------------
@app.route("/audio_notes")
def audio_notes():
    topic = session.get("current_topic", "General Topic")
    name = session.get("user_name", "User")
    return render_template("audio_notes.html", topic=topic, name=name)

@app.route("/generate_audio_notes", methods=["POST"])
def generate_audio_notes():
    """Generate audio notes using text-to-speech"""
    topic = session.get("current_topic", "General Topic")
    user_class = session.get("user_class", "high school")
    interests = session.get("user_interests", "science")

    try:
        # Generate notes content using AI
        prompt = f"""Create comprehensive study notes about "{topic}" for {user_class} students.
        Include:
        1. Introduction (2-3 sentences)
        2. Key concepts (3-4 main points)
        3. Important facts
        4. Summary

        Keep it concise and educational. Student interests: {interests}"""

        process = subprocess.Popen(
            ["ollama", "run", "llama3"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        stdout, stderr = process.communicate(input=prompt.encode("utf-8"), timeout=120)
        notes_text = stdout.decode("utf-8", errors="ignore").strip()
        notes_text = remove_spinner_artifacts(notes_text)

        # Generate audio using pyttsx3 or gTTS
        import pyttsx3

        interest_hash = get_interest_hash(interests.split(","))
        folder_name = f"{topic.replace(' ', '_')}__{interest_hash}"
        audio_folder = os.path.join(app.root_path, "static", "generated_audio", folder_name)
        os.makedirs(audio_folder, exist_ok=True)

        audio_path = os.path.join(audio_folder, "notes_audio.mp3")

        # Initialize text-to-speech engine
        engine = pyttsx3.init()
        engine.setProperty('rate', 150)  # Speed of speech
        engine.setProperty('volume', 0.9)  # Volume level

        # Save audio file
        engine.save_to_file(notes_text, audio_path)
        engine.runAndWait()

        return jsonify({
            "status": "success",
            "audio_url": f"/static/generated_audio/{folder_name}/notes_audio.mp3",
            "notes_text": notes_text
        })

    except Exception as e:
        print(f"❌ Audio generation error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

# -------------------- BOOKS --------------------
@app.route("/books")
def books():
    """Books page where users can upload and interact with books"""
    return render_template("books.html")

@app.route("/upload_book", methods=["POST"])
def upload_book():
    """Handle book file upload"""
    if 'book_file' not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files['book_file']
    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400

    # Save uploaded book
    books_folder = os.path.join(app.root_path, "static", "uploaded_books")
    os.makedirs(books_folder, exist_ok=True)

    filename = file.filename
    filepath = os.path.join(books_folder, filename)
    file.save(filepath)

    # Store in session
    if 'uploaded_books' not in session:
        session['uploaded_books'] = []

    session['uploaded_books'].append({
        'filename': filename,
        'filepath': f"/static/uploaded_books/{filename}"
    })
    session.modified = True

    return jsonify({
        "status": "success",
        "message": "Book uploaded successfully",
        "filename": filename
    })

@app.route("/get_books", methods=["GET"])
def get_books():
    """Get list of uploaded books"""
    books = session.get('uploaded_books', [])
    return jsonify({"books": books})

@app.route("/ask_book_question", methods=["POST"])
def ask_book_question():
    """Ask questions about the book content"""
    data = request.get_json()
    question = data.get("question", "").strip()
    book_context = data.get("book_context", "").strip()

    if not question:
        return jsonify({"error": "No question provided"}), 400

    prompt = f"""Based on the following book content, answer the question clearly and concisely.

Book Content:
{book_context[:2000]}

Question: {question}

Answer:"""

    try:
        process = subprocess.Popen(
            ["ollama", "run", "llama3"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        stdout, stderr = process.communicate(input=prompt.encode("utf-8"), timeout=20)
        answer = stdout.decode("utf-8", errors="ignore").strip()
        answer = remove_spinner_artifacts(answer)

        return jsonify({"answer": answer})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# -------------------- CODING PRACTICE --------------------
@app.route("/coding_practice")
def coding_practice():
    """Coding practice page for kids"""
    return render_template("coding_practice.html")

@app.route("/run_code", methods=["POST"])
def run_code():
    """Execute Python code safely"""
    data = request.get_json()
    code = data.get("code", "").strip()

    if not code:
        return jsonify({"error": "No code provided"}), 400

    try:
        # Create a temporary file to run the code
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(code)
            temp_file = f.name

        # Run the code with timeout
        result = subprocess.run(
            ['python', temp_file],
            capture_output=True,
            text=True,
            timeout=5
        )

        # Clean up
        os.unlink(temp_file)

        output = result.stdout if result.stdout else result.stderr

        return jsonify({
            "status": "success",
            "output": output
        })

    except subprocess.TimeoutExpired:
        return jsonify({"error": "Code execution timed out (5 seconds limit)"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/get_coding_lesson", methods=["POST"])
def get_coding_lesson():
    """Get a coding lesson from AI"""
    data = request.get_json()
    topic = data.get("topic", "Python basics")

    prompt = f"""Create a simple coding lesson about "{topic}" for kids (ages 8-14).
    Include:
    1. Brief explanation (2-3 sentences)
    2. A simple code example
    3. What the code does

    Keep it fun and easy to understand!"""

    try:
        process = subprocess.Popen(
            ["ollama", "run", "llama3"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        stdout, stderr = process.communicate(input=prompt.encode("utf-8"), timeout=200)
        lesson = stdout.decode("utf-8", errors="ignore").strip()
        lesson = remove_spinner_artifacts(lesson)

        return jsonify({"lesson": lesson})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# -------------------- NEWS API --------------------
@app.route("/get_government_news", methods=["GET"])
def get_government_news():
    """Fetch latest government news"""
    try:
        # Using News API (you'll need to sign up for a free API key at newsapi.org)
        # For demo purposes, returning mock data
        news_items = [
            {
                "title": "New Education Policy Updates",
                "description": "Government announces new initiatives for digital education",
                "url": "#",
                "date": "2025-02-10"
            },
            {
                "title": "Scholarship Programs Launched",
                "description": "Merit-based scholarships for students across India",
                "url": "#",
                "date": "2025-02-09"
            },
            {
                "title": "Digital India Initiative Expansion",
                "description": "Smart classrooms to be set up in 10,000 schools",
                "url": "#",
                "date": "2025-02-08"
            }
        ]

        return jsonify({"news": news_items})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# -------------------- USER HANDLING --------------------

@app.route("/save_user", methods=["POST"])
def save_user():
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data received"}), 400
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")
    if not password:
        return jsonify({"error": "Password required"}), 400
    # Check if user already exists
    if os.path.exists(CSV_PATH):
        with open(CSV_PATH, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row["Email"].strip().lower() == email:
                    return jsonify({"error": "Email already registered"}), 409
    # Hash the password
    hashed_password = generate_password_hash(password)
    # Save new user
    file_exists = os.path.isfile(CSV_PATH)
    with open(CSV_PATH, "a", newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow([
                "Name", "Email", "Password", "Phone", "Age", "Gender", "Class", "Interests"
            ])
        writer.writerow([
            data.get("name", ""),
            email,
            hashed_password,
            data.get("phone", ""),
            data.get("age", ""),
            data.get("gender", ""),
            data.get("class", ""),
            ",".join(data.get("interests", []))
        ])
    return jsonify({"message": "Saved"}), 200

@app.route("/login", methods=["POST"])
def login_user():
    data = request.get_json()
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")
    if not os.path.exists(CSV_PATH):
        return jsonify({"error": "No users found"}), 404
    with open(CSV_PATH, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["Email"].strip().lower() == email:
                if check_password_hash(row["Password"], password):
                    # Store full user info in session
                    session["user_name"] = row["Name"]
                    session["user_contact"] = row["Phone"]
                    session["user_age"] = row["Age"]
                    session["user_gender"] = row["Gender"]
                    session["user_class"] = row["Class"]
                    session["user_interests"] = row["Interests"]
                    return jsonify({
                        "name": row["Name"],
                        "email": row["Email"],
                        "phone": row["Phone"],
                        "age": row["Age"],
                        "gender": row["Gender"],
                        "class": row["Class"],
                        "interests": row["Interests"].split(",")
                    }), 200
                else:
                    return jsonify({"error": "Incorrect password"}), 401
    return jsonify({"error": "User not found"}), 404

@app.route("/edit_profile", methods=["GET", "POST"])
def edit_profile():
    if request.method == "POST":
        new_name = request.form.get("name", "").strip()
        new_class = request.form.get("user_class", "").strip()
        new_interests = request.form.getlist("interests")
        email = session.get("user_contact")  # Email or phone used as unique key
        if not email:
            return "Session expired. Please log in again.", 401
        # Update session
        session["user_name"] = new_name
        session["user_class"] = new_class
        session["user_interests"] = new_interests
        # Update CSV
        updated_rows = []
        with open(CSV_PATH, newline='', encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row["Phone"].strip() == email:
                    row["Name"] = new_name
                    row["Class"] = new_class
                    row["Interests"] = ",".join(new_interests)
                updated_rows.append(row)
        with open(CSV_PATH, "w", newline='', encoding="utf-8") as f:
            fieldnames = ["Name", "Email", "Password", "Phone", "Age", "Gender", "Class", "Interests"]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(updated_rows)
        # Render with success flag
        return render_template("edit_profile.html",
                               name=new_name,
                               user_class=new_class,
                               interests=new_interests,
                               success=True)
    # On GET: load session data into form
    return render_template("edit_profile.html",
                           name=session.get("user_name"),
                           user_class=session.get("user_class"),
                           interests=session.get("user_interests", []),
                           success=False)

# -------------------- AI + PDF GENERATION --------------------

@app.route("/ask_ai", methods=["POST"])
def ask_ai():
    data = request.get_json()
    question = data.get("question", "").strip()
    if not question:
        return jsonify({"error": "Empty question"}), 400
    interests = session.get("user_interests", "science, technology")
    topic = session.get("current_topic", "General Learning")
    user_class = session.get("user_class", "high school")

    prompt = f"You are a helpful {user_class} tutor for {topic}. Answer briefly and clearly in 2-3 sentences max. Student interests: {interests}.\n\nQ: {question}\nA:"

    try:
        process = subprocess.Popen(
            ["ollama", "run", "llama3"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        stdout, stderr = process.communicate(input=prompt.encode("utf-8"), timeout=20)
        output = stdout.decode("utf-8", errors="ignore").strip()
        clean_output = remove_spinner_artifacts(output)

        if len(clean_output) > 500:
            clean_output = clean_output[:500] + "..."

        return jsonify({"answer": clean_output})
    except subprocess.TimeoutExpired:
        return jsonify({"answer": f"I'm here to help with {topic}! Could you ask a more specific question about this topic?"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/generate_pdf", methods=["POST"])
def generate_pdf_route():
    topic = session.get("current_topic", "General Topic")
    interests = session.get("user_interests", "science")
    user_class = session.get("user_class", "high school")
    interest_hash = get_interest_hash(interests.split(","))
    folder_name = f"{topic.replace(' ', '_')}__{interest_hash}"
    topic_folder = os.path.join(app.root_path, "static", "generated_pdfs", folder_name)
    pdf_path = os.path.join(topic_folder, "notes.pdf")
    if os.path.exists(pdf_path):
        print(f"📄 PDF already exists for {topic} at {user_class} level")
        return jsonify({
            "status": "ok",
            "message": f"Notes already generated for {user_class} level",
            "folder": folder_name
        })
    try:
        print(f"📚 Generating new PDF for {topic} at {user_class} level...")
        generate_notes_pdf(topic, interests, user_class, topic_folder)
        return jsonify({
            "status": "ok",
            "message": f"Successfully generated {user_class}-level notes",
            "folder": folder_name
        })
    except Exception as e:
        print("❌ PDF Generation Failed:", str(e))
        return jsonify({
            "status": "error",
            "message": f"Failed to generate notes: {str(e)}"
        }), 500

# -------------------- UTILITIES --------------------

def get_interest_hash(interests):
    interests = sorted(i.strip().lower() for i in interests)
    key = ",".join(interests)
    return hashlib.md5(key.encode()).hexdigest()[:8]

def generate_notes_pdf(topic, interests, user_class, topic_folder):
    """Generate PDF notes appropriate for the student's class level"""
    print(f"📚 Starting PDF generation for {user_class} level: {topic}")

    prompt = f"""
    You are a creative educator. Generate engaging, visual and clear **study notes** for the topic \"{topic}\" for {user_class} students.
    Personalize it for a student interested in: {interests}.
    Make the content appropriate for {user_class} level - adjust vocabulary, complexity, and examples accordingly.
    Style: student-friendly, visual, fun (where possible), appropriate for {user_class} level.
    Output format: bullet points or markdown.
    Include practical examples and real-world applications relevant to {interests}.
    """

    print("🤖 Generating content with AI...")
    process = subprocess.Popen(
        ["ollama", "run", "llama3"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    stdout, stderr = process.communicate(prompt.encode('utf-8'))
    content = stdout.decode('utf-8', errors='ignore').strip()

    print("📄 Creating PDF document...")
    os.makedirs(topic_folder, exist_ok=True)
    pdf_path = os.path.join(topic_folder, "notes.pdf")
    def clean_text(text):
        return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)

    # Add title
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, f"Study Notes: {topic}", ln=True, align='C')
    pdf.cell(0, 5, f"Level: {user_class.title()}", ln=True, align='C')
    pdf.ln(10)

    # Add content
    pdf.set_font("Arial", size=12)
    for line in content.splitlines():
        if line.strip():
            pdf.multi_cell(0, 8, txt=clean_text(line))
            pdf.ln(2)
    pdf.output(pdf_path)
    print(f"✅ PDF saved successfully: {pdf_path}")

def remove_spinner_artifacts(text):
    spinner_chars = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
    return re.sub(f"[{re.escape(spinner_chars)}]", "", text).strip()

# -------------------- MAIN --------------------

if __name__ == "__main__":
    print("🚀 Starting Advanced Educational Quiz App...")
    print("📁 Creating necessary directories...")

    # Ensure all directories exist
    os.makedirs("static/generated_pdfs", exist_ok=True)
    os.makedirs("static/generated_videos", exist_ok=True)
    os.makedirs("static/generated_audio", exist_ok=True)
    os.makedirs("static/uploaded_books", exist_ok=True)
    os.makedirs("csv", exist_ok=True)

    print("✅ Application ready!")
    app.run(debug=True, threaded=True)
