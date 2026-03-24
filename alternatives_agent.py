from google.adk.agents import LlmAgent
import os
import requests
from tenacity import retry, stop_after_attempt, wait_exponential_jitter


AV_BASE_URL = "https://www.alphavantage.co/query"
FRED_BASE_URL = "https://api.stlouisfed.org/fred/series/observations"


def _get_av_key():
    key = os.getenv("ALPHA_VANTAGE_API_KEY")
    if not key:
        raise ValueError("ALPHA_VANTAGE_API_KEY environment variable is required")
    return key


def _get_fred_key():
    key = os.getenv("FRED_API_KEY")
    if not key:
        raise ValueError("FRED_API_KEY environment variable is required")
    return key


@retry(stop=stop_after_attempt(3), wait=wait_exponential_jitter(initial=3, max=60), reraise=True)
def _av_request(params: dict) -> dict:
    params["apikey"] = _get_av_key()
    response = requests.get(AV_BASE_URL, params=params, timeout=30)
    response.raise_for_status()
    return response.json()


@retry(stop=stop_after_attempt(3), wait=wait_exponential_jitter(initial=3, max=60), reraise=True)
def _fred_request(series_id: str, limit: int = 24) -> dict:
    params = {
        "series_id": series_id,
        "api_key": _get_fred_key(),
        "file_type": "json",
        "sort_order": "desc",
        "limit": limit,
    }
    response = requests.get(FRED_BASE_URL, params=params, timeout=30)
    response.raise_for_status()
    return response.json()


# --- FRED Housing Tools ---

def housing_prices() -> dict:
    """Get Case-Shiller National Home Price Index (monthly). Tracks changes in the value of residential real estate nationally."""
    return _fred_request("CSUSHPINSA")


def median_home_price() -> dict:
    """Get median sales price of houses sold in the US (quarterly). Key indicator of housing affordability."""
    return _fred_request("MSPUS")


def mortgage_rate_30yr() -> dict:
    """Get 30-year fixed mortgage rate (weekly). Critical factor for housing affordability and demand."""
    return _fred_request("MORTGAGE30US")


def housing_starts() -> dict:
    """Get new privately-owned housing units started (monthly, thousands of units). Indicator of housing supply growth."""
    return _fred_request("HOUST")


def housing_inventory() -> dict:
    """Get monthly supply of new houses (months of supply). Below 6 months indicates a seller's market, above indicates buyer's market."""
    return _fred_request("MSACSR")


def housing_permits() -> dict:
    """Get new privately-owned housing units authorized by building permits (monthly, thousands of units). Leading indicator of future construction."""
    return _fred_request("PERMIT")


# --- Alpha Vantage Commodity & Crypto Tools ---

def commodity_price(commodity: str) -> dict:
    """Get monthly price data for a commodity. Valid values: WTI, BRENT, NATURAL_GAS, COPPER, ALUMINUM, WHEAT, CORN, COTTON, SUGAR, COFFEE."""
    return _av_request({"function": commodity, "interval": "monthly"})


def precious_metal_price(metal: str) -> dict:
    """Get monthly price data for a precious metal. Valid values: GOLD, SILVER."""
    # Alpha Vantage uses function name directly for precious metals (e.g. function=GOLD)
    # but the commodity endpoint works for these too
    function_map = {"GOLD": "GOLD", "SILVER": "SILVER"}
    func = function_map.get(metal.upper(), metal.upper())
    return _av_request({"function": func, "interval": "monthly"})


def crypto_exchange_rate(from_currency: str) -> dict:
    """Get real-time exchange rate for a cryptocurrency to USD. Examples: BTC, ETH, SOL, DOGE, ADA."""
    return _av_request({
        "function": "CURRENCY_EXCHANGE_RATE",
        "from_currency": from_currency,
        "to_currency": "USD",
    })


def crypto_monthly(symbol: str) -> dict:
    """Get monthly OHLCV data for a cryptocurrency. Examples: BTC, ETH, SOL. Returns open, high, low, close, volume."""
    return _av_request({
        "function": "DIGITAL_CURRENCY_MONTHLY",
        "symbol": symbol,
        "market": "USD",
    })


def create_alternatives_agent():
    _get_fred_key()  # fail fast if key is missing

    return LlmAgent(
        model=os.getenv("AGENT_GEMINI_MODEL", "gemini-3-flash-preview"),
        name="alternatives_agent",
        description="Gathers data on alternative investments: real estate/housing market, precious metals, commodities, and cryptocurrencies.",
        instruction=(
            "You are an Alternative Investments Research Agent. Your job is to gather data on non-stock investments. "
            "For real estate/housing questions, use the FRED housing tools: housing_prices, median_home_price, "
            "mortgage_rate_30yr, housing_starts, housing_inventory, housing_permits. "
            "For commodities, use commodity_price (WTI, BRENT, NATURAL_GAS, COPPER, ALUMINUM, WHEAT, CORN, COTTON, SUGAR, COFFEE). "
            "For precious metals, use precious_metal_price (GOLD, SILVER). "
            "For crypto, use crypto_exchange_rate for current price and crypto_monthly for historical data. "
            "For REITs, farmland, or collectibles, report what data you have and note that additional search may be needed. "
            "Provide raw, structured data. Do not interpret the data yourself."
        ),
        tools=[
            housing_prices,
            median_home_price,
            mortgage_rate_30yr,
            housing_starts,
            housing_inventory,
            housing_permits,
            commodity_price,
            precious_metal_price,
            crypto_exchange_rate,
            crypto_monthly,
        ],
    )
