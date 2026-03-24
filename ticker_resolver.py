from google.adk.agents import LlmAgent
from google.adk.tools import google_search
import os

def create_ticker_resolver_agent():
    return LlmAgent(
        model=os.getenv("AGENT_GEMINI_MODEL", "gemini-3-flash-preview"),
        name="ticker_resolver",
        description="Resolves a company name to its stock ticker symbol using Google Search.",
        instruction=(
            "You are a stock ticker symbol resolver. "
            "When given a company name, use google_search to find its official "
            "stock ticker symbol. "
            "Search for '<company name> stock ticker symbol site:finance.yahoo.com OR site:google.com/finance'. "
            "Return only the ticker symbol as plain text."
        ),
        tools=[google_search],
    )
