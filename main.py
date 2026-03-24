import sys
import os
import asyncio
import datetime
from dotenv import load_dotenv
from google.adk.agents import LlmAgent
from google.adk.runners import (
    Runner,
    InMemoryArtifactService,
    InMemoryMemoryService,
)
from google.adk.sessions import DatabaseSessionService
from google.adk.a2a.utils.agent_to_a2a import to_a2a
from google.adk.tools import AgentTool
from google.genai import types
from ticker_resolver import create_ticker_resolver_agent
from research_agent import create_research_agent
from alternatives_agent import create_alternatives_agent
from self_investment_agent import create_self_investment_agent
from analyst_agent import create_analyst_agent

load_dotenv(os.path.join(os.path.dirname(__file__), '.env'), override=True)
if os.getenv("GOOGLE_API_KEY"):
    os.environ["GOOGLE_API_KEY"] = os.getenv("GOOGLE_API_KEY")

DEFAULT_MODEL = "gemini-3-flash-preview"

def _load_investor_profile():
    profile_path = os.path.join(os.path.dirname(__file__), "investor_profile.md")
    if os.path.exists(profile_path):
        with open(profile_path) as f:
            return f.read()
    return ""

def get_current_datetime():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def create_root_agent():
    ticker_resolver_agent = create_ticker_resolver_agent()
    research_agent_obj = create_research_agent()
    alternatives_agent_obj = create_alternatives_agent()
    self_investment_agent_obj = create_self_investment_agent()
    analyst_agent_obj = create_analyst_agent()

    investor_profile = _load_investor_profile()

    SYSTEM_INSTRUCTION = (
        "You are a sophisticated Financial AI Agent covering stocks, alternative investments, AND self-investment. "
        "You are advising a specific investor. Tailor all recommendations to their situation:\n\n"
        f"{investor_profile}\n\n"
        "Route questions as follows:\n"
        "- Stocks/companies: use ticker_resolver to get the symbol, then research_agent for data, then analyst_agent for the report.\n"
        "- Alternative investments (real estate, housing market, precious metals, commodities, crypto): "
        "use alternatives_agent to gather data, then analyst_agent for the report.\n"
        "- REITs or other traded alternatives: use ticker_resolver to find the symbol, then research_agent for stock data, "
        "plus alternatives_agent for the broader market context.\n"
        "- Self-investment (certifications, skills development, career moves, education, salary benchmarking): "
        "use self_investment_agent to gather data, then analyst_agent for the report.\n"
        "- Portfolio allocation including human capital (e.g. 'should I invest in gold or a GCP cert?'): "
        "use BOTH the relevant financial agents (research_agent and/or alternatives_agent) AND self_investment_agent "
        "to gather data, then analyst_agent for the combined report.\n"
        "- Mixed/portfolio questions (e.g. 'compare Apple vs gold'): use BOTH research_agent and alternatives_agent "
        "to gather data, then analyst_agent for the combined report.\n"
        "Do not interpret the data yourself; always use the analyst_agent for the final recommendation. "
        "Use the Alpha Vantage tools conservatively to respect rate limits."
    )

    return LlmAgent(
        model=os.getenv("AGENT_GEMINI_MODEL", DEFAULT_MODEL),
        name="financial_root_agent",
        description="A full-service financial analyst covering stocks, real estate, metals, commodities, crypto, and self-investment.",
        instruction=SYSTEM_INSTRUCTION,
        tools=[
            AgentTool(ticker_resolver_agent),
            AgentTool(research_agent_obj),
            AgentTool(alternatives_agent_obj),
            AgentTool(self_investment_agent_obj),
            AgentTool(analyst_agent_obj),
            get_current_datetime,
        ],
    )

def _get_db_path():
    return os.path.join(os.path.dirname(__file__), "sessions.db")


async def chat_loop():
    print("--- Financial AI Agent v2 (CLI Chat Mode) ---")
    print("Sessions are saved locally. Use 'exit' or 'quit' to leave.\n")

    root_agent = create_root_agent()
    db_url = f"sqlite:///{_get_db_path()}"
    session_service = DatabaseSessionService(db_url=db_url)

    # Resume existing session or create a new one
    user_id = "user_1"
    app_name = "fin_app"
    existing = await session_service.list_sessions(app_name=app_name, user_id=user_id)

    if existing and existing.sessions:
        session = await session_service.get_session(
            app_name=app_name, user_id=user_id, session_id=existing.sessions[0].id
        )
        print(f"Resumed session: {session.id}")
    else:
        session = await session_service.create_session(
            app_name=app_name, user_id=user_id
        )
        print(f"New session: {session.id}")

    runner = Runner(
        app_name=app_name,
        agent=root_agent,
        session_service=session_service,
        artifact_service=InMemoryArtifactService(),
        memory_service=InMemoryMemoryService(),
    )

    while True:
        try:
            user_input = input("\nYou: ")
            if user_input.lower() in ["exit", "quit"]:
                break
            if user_input.lower() == "new":
                session = await session_service.create_session(
                    app_name=app_name, user_id=user_id
                )
                print(f"Started new session: {session.id}")
                continue

            print("\nAnalyst is working...")
            async for event in runner.run_async(
                user_id=user_id,
                session_id=session.id,
                new_message=types.Content(parts=[types.Part(text=user_input)], role="user"),
            ):
                if hasattr(event, "content") and event.content:
                    for part in event.content.parts:
                        if part.text:
                            print(part.text, end="", flush=True)
            print()
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"\nError: {e}")

if __name__ == "__main__":
    if "--chat" in sys.argv:
        asyncio.run(chat_loop())
    else:
        import uvicorn
        root_agent = create_root_agent()
        port = int(os.getenv("AGENT_PORT", 10000))
        print(f"Starting A2A service on port {port}...")
        app = to_a2a(root_agent, port=port)
        uvicorn.run(app, host="0.0.0.0", port=port)

