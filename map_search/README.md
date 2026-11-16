# Google Maps Search using MCP & Local Ollama

This module integrates a Google Maps MCP (Model Context Protocol) server with a local Ollama AI agent.

## Components

- `maps_mcp_server.py`: FastMCP server exposing Google Maps tools:
  - `maps_search_places(query)`: Search for places (cafes, restaurants, landmarks) using Google Places API.
  - `maps_geocode(address)`: Convert address into latitude and longitude coordinates.
  - `maps_directions(origin, destination, mode)`: Get directions, distance, and duration.
- `mcp_agent.py`: AI agent client using `praisonaiagents` connected to `maps_mcp_server.py` over stdio and powered by local Ollama (`gemma4:latest`).
- `requirements.txt`: Python package requirements.

## Configuration

Set your Google Maps API key in `map_search/.env`:
```bash
GOOGLE_MAPS_API_KEY=your_api_key_here
```

## How to Run

### Via Docker Container (`ai`)
```bash
docker exec -it -w /var/www/ai/map_search ai python3 mcp_agent.py "Find popular coffee shops near Connaught Place, New Delhi"
```

Or interactively:
```bash
docker exec -it -w /var/www/ai/map_search ai python3 mcp_agent.py
```

### Directly on Host
Ensure Ollama is running locally with the `gemma4:latest` model, install dependencies, and run:
```bash
pip install -r requirements.txt
python3 mcp_agent.py "Find top coffee shops near Connaught Place, New Delhi"
```
