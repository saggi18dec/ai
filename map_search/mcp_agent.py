import json
import os
import re
import sys
from dotenv import load_dotenv

# Compatibility shim for mcp with praisonaiagents
try:
    try:
        import mcp.types as _mcp_types
    except ImportError:
        import mcp_types as _mcp_types
        import mcp as _mcp_pkg
        _mcp_pkg.types = _mcp_types
        sys.modules["mcp.types"] = _mcp_types

    if hasattr(_mcp_types, "Tool") and not hasattr(_mcp_types.Tool, "inputSchema"):
        _mcp_types.Tool.inputSchema = property(lambda self: getattr(self, "input_schema", {}))
    if hasattr(_mcp_types, "CallToolResult") and not hasattr(_mcp_types.CallToolResult, "isError"):
        _mcp_types.CallToolResult.isError = property(lambda self: getattr(self, "is_error", False))
except Exception:
    pass

from praisonaiagents import Agent, MCP
from praisonaiagents.llm import LLM

# -----------------------------------------------------------------------------
# 1. Environment & Configuration
# -----------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(SCRIPT_DIR, ".env"))

# Retrieve endpoint configurations from .env
docker_url = os.getenv("DOCKER_BASE_URL", "http://host.docker.internal:11434/v1")
local_url = os.getenv("LOCAL_BASE_URL", "http://localhost:11434/v1")

# Use Docker endpoint when inside a container, otherwise local endpoint
base_url = docker_url if os.path.exists("/.dockerenv") else local_url

MODEL = os.getenv("MODEL", "gemma4:latest")
API_KEY = os.getenv("API_KEY", "ollama")
GOOGLE_MAPS_API_KEY = os.environ.get("GOOGLE_MAPS_API_KEY", "")

# Configure Ollama / OpenAI environment for praisonai / LiteLLM
ollama_host = base_url.replace("/v1", "").rstrip("/")
os.environ["OLLAMA_API_BASE"] = ollama_host
os.environ["OPENAI_BASE_URL"] = base_url
os.environ["OPENAI_API_KEY"] = API_KEY


def _extract_raw_tool_call(response: str):
    """Detect if the LLM output raw tool_calls JSON text instead of executing."""
    if not response:
        return None
    text = str(response).strip()
    if "tool_calls" not in text:
        return None
    try:
        match = re.search(r'\{.*"tool_calls"\s*:\s*\[.*\]\s*\}', text, re.DOTALL)
        if match:
            data = json.loads(match.group(0))
            if "tool_calls" in data and len(data["tool_calls"]) > 0:
                return data["tool_calls"][0]
    except Exception:
        pass
    return None


def _execute_fallback_tool(tool_call: dict) -> str:
    """Directly execute tool if model produced raw JSON instead of native execution."""
    name = tool_call.get("name")
    args = tool_call.get("arguments", {})
    import maps_mcp_server
    if name == "maps_search_places":
        return maps_mcp_server.maps_search_places(**args)
    elif name == "maps_geocode":
        return maps_mcp_server.maps_geocode(**args)
    elif name == "maps_directions":
        return maps_mcp_server.maps_directions(**args)
    return ""


def run_maps_assistant(query: str):
    # print(f"Connecting at {base_url} [model: {MODEL}] with Google Maps MCP...")

    server_script = os.path.join(SCRIPT_DIR, "maps_mcp_server.py")
    model_name = f"ollama/{MODEL}" if not MODEL.startswith("ollama/") else MODEL

    llm_instance = LLM(
        model=model_name,
        temperature=0.0,
    )

    instructions = (
        "You are an expert Google Maps travel and local search assistant.\n"
        "Rules:\n"
        "1. For any location or place search query, call the `maps_search_places` tool with the full search query.\n"
        "2. When presenting results, always display the full list of places returned by the tool.\n"
        "3. Include the name, rating, address, and contact details for each place."
    )

    maps_agent = Agent(
        instructions=instructions,
        model=llm_instance,
        output="silent",
        tools=MCP(
            f"{sys.executable} {server_script}",
            env={"GOOGLE_MAPS_API_KEY": os.environ.get("GOOGLE_MAPS_API_KEY", "")}
        )
    )

    # print(f"\nUser Query: {query}\nProcessing with local Ollama + MCP...")
    response = maps_agent.start(query)

    # Check if local model returned raw JSON tool_calls instead of executing
    raw_tc = _extract_raw_tool_call(response)
    if raw_tc:
        fallback_res = _execute_fallback_tool(raw_tc)
        if fallback_res:
            response = fallback_res

    # print("\n--- AI Response ---")
    return response


if __name__ == "__main__":
    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
    else:
        query = input("enter your query: ")
    print(run_maps_assistant(query))
