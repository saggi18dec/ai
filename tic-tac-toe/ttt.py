import os
import openai
from dotenv import load_dotenv

# -----------------------------------------------------------------------------
# 1. Environment & Client Configuration
# -----------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(SCRIPT_DIR, ".env"))

# Retrieve endpoint configurations from .env
docker_url = os.getenv("DOCKER_BASE_URL")
local_url = os.getenv("LOCAL_BASE_URL")

# Use Docker endpoint when inside a container, otherwise local endpoint
base_url = docker_url if os.path.exists("/.dockerenv") else local_url

MODEL = os.getenv("MODEL")
API_KEY = os.getenv("API_KEY")

client = openai.OpenAI(
    base_url=base_url,
    api_key=API_KEY,
)

def load_skill_file(filename="tic_tac_toe_skill.md"):
    """Reads the markdown skill file to use as instructions for the LLM."""
    filepath = os.path.join(SCRIPT_DIR, filename)
    if not os.path.exists(filepath):
        filepath = filename
    if not os.path.exists(filepath):
        print(f"Error: Could not find '{filename}' in '{SCRIPT_DIR}'.")
        print("Please make sure your tic_tac_toe_skill.md file is saved right here.")
        exit(1)

    with open(filepath, "r", encoding="utf-8") as f:
        return f.read()


def run_tic_tac_toe():
    # 1. Load the skill instructions
    skill_instructions = load_skill_file("tic_tac_toe_skill.md")

    print(f"Connecting at {base_url} [model: {MODEL}]...")

    # 2. Initialize conversation history with the skill file as the system prompt
    messages = [
        {
            "role": "system",
            "content": f"You are an AI assistant loaded with the following skill and rules. You must strictly follow them:\n\n{skill_instructions}",
        },
        {
            "role": "user",
            "content": "Let's play a game of Tic-Tac-Toe! Start the game, show the board, and let's figure out who goes first.",
        },
    ]

    # 3. Get the opening response
    response = client.chat.completions.create(
        model=MODEL,
        messages=messages,
    )

    ai_message = response.choices[0].message.content

    print(f"\n{ai_message}")
    messages.append({"role": "assistant", "content": ai_message})

    # 4. Main interactive game loop
    while True:
        try:
            user_input = input("\nYour input: ")
            if user_input.lower() in ["exit", "quit"]:
                print("Exiting game. Thanks for playing!")
                break

            # Append user response to history
            messages.append({"role": "user", "content": user_input})

            # Send updated conversation back
            response = client.chat.completions.create(
                model=MODEL,
                messages=messages,
            )

            ai_message = response.choices[0].message.content

            print(f"\n{ai_message}")
            messages.append({"role": "assistant", "content": ai_message})

        except KeyboardInterrupt:
            print("\nGame interrupted. Goodbye!")
            break


if __name__ == "__main__":
    run_tic_tac_toe()
