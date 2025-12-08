import subprocess
import time
import sys

# -------------------- Start Ollama server --------------------
def start_ollama_server():
    try:
        # Start ollama serve in background
        subprocess.Popen(
            ["ollama", "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        print("🚀 Starting Ollama server...")
        time.sleep(3)  # wait for server to boot
    except Exception as e:
        print(f"❌ Failed to start Ollama server: {e}")
        sys.exit(1)

# -------------------- Run prompt with llama3 --------------------
def ask_ollama(prompt):
    try:
        process = subprocess.Popen(
            ["ollama", "run", "llama3"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        stdout, stderr = process.communicate(input=prompt.encode("utf-8"), timeout=60)
        output = stdout.decode("utf-8", errors="ignore").strip()
        return clean_output(output)
    except subprocess.TimeoutExpired:
        return "⏳ Ollama timed out."
    except Exception as e:
        return f"❌ Error: {str(e)}"

# -------------------- Clean spinner/artifacts --------------------
def clean_output(text):
    # Remove spinner characters like ⠇ ⠸ ⠴ etc
    spinners = ["⠇", "⠸", "⠴", "⠦", "⠙", "⠹", "⠋"]
    for s in spinners:
        text = text.replace(s, "")
    return text.strip()

# -------------------- Main loop --------------------
if __name__ == "__main__":
    start_ollama_server()
    print("💬 Chat with Llama3 (type 'exit' to quit)")

    while True:
        user_input = input("You: ").strip()
        if user_input.lower() == "exit":
            print("👋 Bye!")
            break

        response = ask_ollama(user_input)
        print(f"AI: {response}")
