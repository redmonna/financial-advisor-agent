from google.adk.agents import LlmAgent
import os
import requests
from tenacity import retry, stop_after_attempt, wait_exponential_jitter


BASE_URL = "https://www.alphavantage.co/query"


def _get_api_key():
    key = os.getenv("ALPHA_VANTAGE_API_KEY")
    if not key:
        raise ValueError("ALPHA_VANTAGE_API_KEY environment variable is required")
    return key


@retry(stop=stop_after_attempt(3), wait=wait_exponential_jitter(initial=3, max=60), reraise=True)
def _av_request(params: dict) -> dict:
    params["apikey"] = _get_api_key()
    response = requests.get(BASE_URL, params=params, timeout=30)
    response.raise_for_status()
    return response.json()


def global_quote(symbol: str) -> dict:
    """Get the latest price, volume, and change data for a stock symbol."""
    return _av_request({"function": "GLOBAL_QUOTE", "symbol": symbol})


def company_overview(symbol: str) -> dict:
    """Get company fundamentals: market cap, P/E ratio, EPS, sector, description, and more."""
    return _av_request({"function": "OVERVIEW", "symbol": symbol})


def earnings(symbol: str) -> dict:
    """Get quarterly and annual earnings history for a stock symbol."""
    return _av_request({"function": "EARNINGS", "symbol": symbol})


def news_sentiment(tickers: str) -> dict:
    """Get news articles and sentiment scores for given ticker(s). Pass comma-separated tickers like 'AAPL' or 'AAPL,MSFT'."""
    return _av_request({"function": "NEWS_SENTIMENT", "tickers": tickers})


def create_research_agent():
    _get_api_key()  # fail fast if key is missing

    return LlmAgent(
        model=os.getenv("AGENT_GEMINI_MODEL", "gemini-3-flash-preview"),
        name="research_agent",
        description="Gathers financial data and news using Alpha Vantage tools.",
        instruction=(
            "You are a Financial Research Agent. Your sole job is to gather data. "
            "Use 'global_quote', 'company_overview', 'earnings', and "
            "'news_sentiment' to collect facts for the given stock symbol. "
            "Provide raw, structured data. Do not interpret the data yourself."
        ),
        tools=[global_quote, company_overview, earnings, news_sentiment],
    )
