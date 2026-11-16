# Indian Stock Momentum Research Agent

An equity research AI system using CrewAI multi-agent orchestration and Google ADK to analyze Nifty 100 constituents and identify top momentum stocks.

## Components

- `agent.py`: CrewAI multi-agent coordinator (Data Downloader, Momentum Analyst, Investment Strategist) and Google ADK root agent.
- `tools/stock_tools.py`: Historical data downloader tool and quantitative momentum ranking tool.
- `requirements.txt`: Python package requirements.

## Configuration

Set your model and API keys in `stock_agent/.env`:
```bash
STOCKS_MODEL=groq/openai/gpt-oss-120b
STOCKS_API_KEY=your_api_key_here
```

## How to Run

### Directly on Host
```bash
cd ai
pip install -r requirements.txt
adk run stock_agent.py
```
