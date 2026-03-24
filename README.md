# Financial AI Agent v2 (Google ADK + MCP + A2A)

A multi-agent financial advisory system built with Google's Agent Development Kit (ADK), Model Context Protocol (MCP), and Agent-to-Agent (A2A) protocol.

## Architecture

1. **Ticker Resolver Agent:** Uses Google Search to find ticker symbols for company names.
2. **Research Agent:** Connects to the Alpha Vantage MCP server to gather structured financial data.
3. **Analyst Agent:** Interprets data and provides buy/sell/hold recommendations.
4. **Alternatives Agent:** Evaluates alternative investments (real estate, precious metals, etc.).
5. **Self-Investment Agent:** Analyzes career development and human capital optimization using BLS and O*NET data.
6. **Root Agent:** Orchestrates the sub-agents and exposes the system as an A2A service.

## Prerequisites

- Python 3.13+
- API keys (all free tier available):
  - [Google AI API Key](https://aistudio.google.com/apikey) — for Gemini models and Google Search
  - [Alpha Vantage](https://www.alphavantage.co/support/#api-key) — stock/financial data
  - [FRED](https://fred.stlouisfed.org/docs/api/api_key.html) — housing and economic data
  - [BLS](https://data.bls.gov/registrationEngine/) — occupation wage and outlook data
  - [O*NET Web Services](https://services.onetcenter.org/) — skills and occupation data

## Setup

1. Clone this repository:
   ```bash
   git clone https://github.com/redmonna/financial-advisor-agent.git
   cd financial-advisor-agent
   ```

2. Create a virtual environment and install dependencies:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

3. Copy the example config files and fill in your details:
   ```bash
   cp .env.example .env
   cp investor_profile.example.md investor_profile.md
   ```

4. Edit `.env` with your API keys.

5. Edit `investor_profile.md` with your personal financial information. This file is gitignored and will never be committed.

6. Run the A2A service:
   ```bash
   python main.py
   ```

7. If you use the ADK Workbench, it loads the packaged `financial_ai_v2/agent.py` entrypoint.

## Usage

Once the service is running, you can query it via the A2A protocol (Port 10000).
The root agent handles the entire workflow:

- **Input:** "Analyze Nvidia for me"
- **Process:**
  - Ticker Resolver finds "NVDA"
  - Research Agent pulls financial data
  - Analyst Agent generates recommendations

- **Input:** "Should I invest in real estate or pay down my mortgage?"
- **Process:**
  - Alternatives Agent evaluates real estate market conditions
  - Self-Investment Agent considers career/income trajectory
  - Analyst Agent provides holistic recommendation

## Project Structure

```
├── main.py                      # A2A service entry point and root agent
├── ticker_resolver.py           # Ticker symbol resolution agent
├── research_agent.py            # Financial data research via Alpha Vantage MCP
├── analyst_agent.py             # Analysis and recommendation agent
├── alternatives_agent.py        # Alternative investment evaluation
├── self_investment_agent.py     # Career/human capital optimization
├── financial_ai_v2/             # ADK Workbench package
│   ├── __init__.py
│   └── agent.py
├── investor_profile.example.md  # Template — copy to investor_profile.md
├── .env.example                 # Template — copy to .env
├── requirements.txt             # Python dependencies
└── README.md
```

## License

MIT
