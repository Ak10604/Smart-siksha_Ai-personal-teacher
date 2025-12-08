import os
import csv

def initialize_databases():
    """Create necessary CSV files if they don't exist."""
    os.makedirs("csv", exist_ok=True)

    # User database
    if not os.path.exists("csv/users.csv"):
        with open("csv/users.csv", "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "Name", "Email", "Password", "Phone", "Age", "Gender", 
                "Class", "Interests", "CompletedTopics", "QuizScores"
            ])

    # Badge database
    if not os.path.exists("csv/badges.csv"):
        with open("csv/badges.csv", "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["UserID", "BadgeName", "DateEarned"])

    # Leaderboard database (can be generated from users.csv, but this is for explicit tracking)
    if not os.path.exists("csv/leaderboard.csv"):
        with open("csv/leaderboard.csv", "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["UserID", "TotalScore", "Rank"])

    # Chat History database
    if not os.path.exists("csv/chat_history.csv"):
        with open("csv/chat_history.csv", "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["UserID", "Timestamp", "Question", "Answer"])