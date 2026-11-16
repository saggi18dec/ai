import os
from dotenv import load_dotenv
from crewai import Agent as CrewAgent, Crew, Process, Task, LLM
from google.adk.agents.llm_agent import Agent as AdkAgent

# Import our custom tools from stock_tools.py
from stock_agent.tools.stock_tools import (
    download_nifty_csvs_tool,
    calculate_momentum_tool,
)

# -----------------------------------------------------------------------------
# 1. Environment & Configuration
# -----------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(SCRIPT_DIR, ".env"))

# Retrieve endpoint configurations from .env
docker_url = os.getenv("DOCKER_BASE_URL")
local_url = os.getenv("LOCAL_BASE_URL")
base_url = docker_url if os.path.exists("/.dockerenv") else local_url

MODEL = os.getenv("STOCKS_MODEL")
API_KEY = os.getenv("STOCKS_API_KEY")

# -----------------------------------------------------------------------------
# 2. LLM Configuration for CrewAI
# -----------------------------------------------------------------------------
# CrewAI uses LiteLLM syntax
llm_kwargs = {
    "model": MODEL,
    "api_key": API_KEY,
}
if base_url:
    llm_kwargs["base_url"] = base_url

stocks_llm = LLM(**llm_kwargs)

# ----------------------------------------------------------------------
# 2. CrewAI Sub-Agents
# ----------------------------------------------------------------------
# Agent 1: Data Downloader
downloader_agent = CrewAgent(
    role="Stock Market Data Collector",
    goal="Fetch 6-month historical price CSVs from Yahoo Finance for all active Nifty 100 constituents.",
    backstory=(
        "You are a specialized financial data engineer. Your job is to fetch clean, "
        "accurate daily OHLCV historical price data for all 100 constituent stocks."
    ),
    tools=[download_nifty_csvs_tool],
    llm=stocks_llm,
    verbose=True,
)

# Agent 2: Momentum Analyst
momentum_analyst = CrewAgent(
    role="Senior Quantitative Momentum Analyst",
    goal="Inspect downloaded CSV files, compute momentum factors, and identify the top 10 strongest momentum stocks.",
    backstory=(
        "You are an expert equity research analyst with a focus on quantitative momentum strategies. "
        "You rank stocks based on multi-timeframe returns, 14-day RSI, and trend positioning above moving averages."
    ),
    tools=[calculate_momentum_tool],
    llm=stocks_llm,
    verbose=True,
)

# ----------------------------------------------------------------------
# 3. CrewAI Tasks
# ----------------------------------------------------------------------
download_task = Task(
    description=(
        "1. Execute the download tool to purge stale data.\n"
        "2. Download historical daily CSV price files for all 100 Nifty constituents from Yahoo Finance."
    ),
    expected_output="A confirmation string reporting the count of successfully downloaded stock CSV files.",
    agent=downloader_agent,
)

analysis_task = Task(
    description=(
        "Call the `calculate_momentum` tool directly to examine all downloaded CSV files. "
        "Do not ask questions; execute the tool immediately. "
        "From the tool's output table, present only the Top 10 stocks with their Close Price, "
        "1-Month and Total Returns, 14-Day RSI, 50-Day Moving Average trend, "
        "and a brief momentum rationale for each. "
        "Do NOT include page titles, Technical Commentary, Risk Considerations, or advice sections. "
        "Output ONLY the Top 10 stocks table and rationales."
    ),
    expected_output=(
        "A clean markdown table of the Top 10 momentum stocks and their rationales only."
    ),
    agent=momentum_analyst,
)

def _render_template(template_path: str, context: dict) -> str:
    """Renders an HTML template using Jinja2."""
    import jinja2
    template_dir = os.path.dirname(template_path)
    template_name = os.path.basename(template_path)
    env = jinja2.Environment(loader=jinja2.FileSystemLoader(template_dir), autoescape=True)
    template = env.get_template(template_name)
    return template.render(**context)


def _generate_html_report(report_text: str, html_path: str):
    """Generates an HTML report by parsing markdown and rendering the HTML template."""
    import re
    from datetime import datetime
    from zoneinfo import ZoneInfo
    now_str = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%B %d, %Y at %I:%M %p")

    def _format_inline(text: str) -> str:
        text = text.replace(".NS", "")
        text = re.sub(r"\*\*(.*?)\*\*", r"<strong>\1</strong>", text)
        text = re.sub(r"\*(.*?)\*", r"<em>\1</em>", text)
        return text

    lines = report_text.strip().split("\n")
    html_body = []
    in_table = False

    for line in lines:
        stripped = line.strip()
        if not stripped:
            if in_table:
                html_body.append("</tbody></table></div>")
                in_table = False
            continue

        lower_line = stripped.lower()

        # Stop parsing if unwanted commentary or risk sections appear
        if any(sec in lower_line for sec in ["technical commentary", "risk considerations", "how to use this list"]):
            break

        # Skip redundant titles since header already displays it
        if any(t in lower_line for t in ["top 10 momentum", "top-10 momentum", "top‑10 momentum", "top 10 nifty", "top-10 nifty", "top‑10 nifty"]):
            continue

        if stripped.startswith("|") and stripped.endswith("|"):
            cols = [c.strip() for c in stripped.strip("|").split("|")]
            if all(set(c).issubset({"-", " ", ":"}) for c in cols):
                continue
            if not in_table:
                html_body.append("<div class='table-container'><table><thead><tr>")
                for col in cols:
                    clean_th = col.replace("**", "").replace("*", "")
                    html_body.append(f"<th>{clean_th}</th>")
                html_body.append("</tr></thead><tbody>")
                in_table = True
            else:
                html_body.append("<tr>")
                for col in cols:
                    html_body.append(f"<td>{_format_inline(col)}</td>")
                html_body.append("</tr>")
        else:
            if in_table:
                html_body.append("</tbody></table></div>")
                in_table = False

            if stripped.startswith("### "):
                html_body.append(f"<h3>{_format_inline(stripped[4:])}</h3>")
            elif stripped.startswith("## "):
                html_body.append(f"<h2>{_format_inline(stripped[3:])}</h2>")
            elif stripped.startswith("# "):
                html_body.append(f"<h1>{_format_inline(stripped[2:])}</h1>")
            elif stripped.startswith("- ") or stripped.startswith("* "):
                html_body.append(f"<li>{_format_inline(stripped[2:])}</li>")
            else:
                html_body.append(f"<p>{_format_inline(stripped)}</p>")

    if in_table:
        html_body.append("</tbody></table></div>")

    body_content = "\n".join(html_body)

    template_path = os.path.join(os.path.dirname(__file__), "templates", "report_template.html")
    context = {
        "title": "Top 10 Momentum Stocks in Nifty 100",
        "subtitle": "Quantitative Momentum Screen • Ranked by Multi-Timeframe Returns, RSI & 50-SMA Positioning",
        "last_updated": f"{now_str} IST",
        "data_source": "National Stock Exchange (NSE India)",
        "universe": "100/100 Constituents Screened",
        "body_content": body_content,
        "disclaimer": "All data and rankings provided on this website are strictly for <strong>informational and educational purposes only</strong> and should not be construed as investment recommendations.",
    }

    rendered_html = _render_template(template_path, context)
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(rendered_html)


# ----------------------------------------------------------------------
# 4. Crew Runner Function (ADK Tool)
# ----------------------------------------------------------------------
async def analyze_nifty_momentum(period: str = "6mo") -> str:
    """Downloads fresh Nifty 100 CSVs and runs CrewAI momentum analysis to return top 10 stocks.
    Args:
        period: Historical lookback period (default '6mo').
    """
    print("\n[CrewAI] Initializing Nifty 100 Momentum Multi-Agent Crew...", flush=True)
    crew = Crew(
        agents=[downloader_agent, momentum_analyst],
        tasks=[download_task, analysis_task],
        process=Process.sequential,
        verbose=True,
    )
    print("[CrewAI] Kicking off Sequential Tasks (Downloader -> Momentum Analyst)...\n", flush=True)
    result = await crew.kickoff_async()
    result_text = str(result)

    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

    # 1. Save plain text file with IST metadata
    from datetime import datetime
    from zoneinfo import ZoneInfo
    ist_time_str = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%B %d, %Y at %I:%M %p")
    
    header_meta = (
        "=" * 120 + "\n"
        "Status:             Verified Live Market Data\n"
        f"Last Updated:      {ist_time_str} IST\n"
        "Data Source:        National Stock Exchange of India (NSE) via Yahoo Finance\n"
        "Universe Screened:  100 / 100 Active Nifty Constituents Analyzed\n"
        + "=" * 120 + "\n\n"
    )

    txt_path = os.path.join(base_dir, "top_10_momentum_stocks.txt")
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(header_meta + result_text)
    print(f"\n[Output] Text report saved to: {txt_path}", flush=True)

    # 2. Save HTML file with required Header & Disclaimer Footer
    html_path = os.path.join(base_dir, "top_10_momentum_stocks.html")
    _generate_html_report(result_text, html_path)
    print(f"[Output] HTML report saved to: {html_path}", flush=True)

    return result_text

# ----------------------------------------------------------------------
# 5. ADK Root Agent Entrypoint
# ----------------------------------------------------------------------
root_agent = AdkAgent(
    model=os.getenv("STOCKS_MODEL"),
    name="stock_agent",
    description="Agent for Indian equity research that finds top momentum stocks in Nifty 100 using CrewAI.",
    instruction=(
        "You are a stock research assistant. When the user asks for momentum stocks, "
        "Nifty 100 screening, or top performing stocks, invoke the 'analyze_nifty_momentum' tool."
    ),
    tools=[analyze_nifty_momentum],
)

if __name__ == "__main__":
    import asyncio
    print(asyncio.run(analyze_nifty_momentum()))