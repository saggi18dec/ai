# Tic-Tac-Toe AI Agent

An interactive terminal-based Tic-Tac-Toe AI agent powered by local Ollama or OpenAI-compatible endpoints with specialized skill instructions.

## Components

- `ttt.py`: Main interactive game agent script.
- `tic_tac_toe_skill.md`: System skill prompt and gameplay rules loaded by the agent.
- `requirements.txt`: Python package requirements.

## Configuration

Configure endpoints in `tic-tac-toe/.env`:
```bash
DOCKER_BASE_URL=http://host.docker.internal:11434/v1
LOCAL_BASE_URL=http://localhost:11434/v1
MODEL=gemma4:latest
API_KEY=ollama
```
See `.env.example` for reference.

## How to Run

### Via Docker Container (`ai`)
```bash
docker exec -it -w /var/www/ai/tic-tac-toe ai python3 ttt.py
```

### Directly on Host
```bash
cd ~/workspace/ai/tic-tac-toe
pip install -r requirements.txt
python3 ttt.py
```
