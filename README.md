🎓 Smart-Siksha — AI Personal Teacher

Personalized Learning • Automatic Notes • AI Quiz • Video Lessons • Counselling • Gamified Learning

Smart-Siksha is an AI-powered educational platform that adapts to each student’s:
✔ Topic preference
✔ Age/Class
✔ Interests
✔ Learning style

It generates notes, videos, quizzes, counselling, and tracks student progress with badges & points.

🚀 Features
📌 1. Smart User Profile

Name, age, class, contact, and interests stored securely

Auto-personalized content

🧠 2. AI Quiz Generation (Ollama-LLama3)

Generates 10 unique questions every time

Smart difficulty scaling based on last attempt

Stores results in database (SQLite)

Results tracking & improvement recommendations

Supports fallback quiz when model fails

✍️ 3. Personalized AI Notes (PDF)

Topic + age + interests based explanation

Stored at /static/generated_pdfs/...

🎥 4. Auto Video Lesson Generation

AI image generation (Stable Diffusion)

Voice narration (Edge-TTS / pyttsx3 fallback)

Captions + music + transitions

Live progress tracker (/get_generation_progress)

Stored at /static/generated_videos/...

🤖 5. Counselling & Suggestions

AI recommends study tips based on:

Quiz performance

Weak topics

Learning progress

🏆 6. Gamification

Earn points & badges

Leaderboard ranking

Tracks usage of quizzes, videos & notes

📁 Project Folder Structure
Smart-Siksha/
│── app.py                      # Main Flask App
│── templates/                  # HTML Templates
│── static/
│    ├── generated_pdfs/
│    ├── generated_videos/
│    ├── generated_audio/
│    ├── uploaded_books/
│
├── csv/
│    ├── users.csv              # User database (CSV)
│    ├── quizzes.db             # Quiz database (SQLite)
│
└── README.md

🛠️ Tech Stack
Component	Tech
Frontend	HTML, CSS, JS, Bootstrap
Backend	Flask
Database	CSV + SQLite
Quiz & AI	Ollama-Llama3/Local AI
Video	Stable Diffusion, FFmpeg
Text to Speech	Edge-TTS / pyttsx3
PDF Generation	FPDF
🔧 Installation & Setup
1️⃣ Clone Repository
git clone https://github.com/Ak10604/Smart-siksha_Ai-personal-teacher.git
cd Smart-siksha_Ai-personal-teacher

2️⃣ Install Required Libraries
pip install -r requirements.txt


If you don’t have requirements.txt, I can generate one.

3️⃣ Install Local AI (Ollama)
https://ollama.com/download


Then pull Llama3:

ollama pull llama3

4️⃣ Run App
python app.py

⚠️ Dependencies Required for AI Video
pip install diffusers torch transformers accelerate opencv-python moviepy


Also install FFmpeg:

https://www.ffmpeg.org/download.html

💡 Contribution

Want to improve Smart-Siksha?

Fork the repo

Add features

Submit Pull Request 🎉

📄 License

📌 Add license here (MIT recommended).
I can create a LICENSE file too if you want.

🌟 Show Support

If you like the project, ⭐ star this repository!
