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

### Option 1: A2A Protocol (Port 10000)

```bash
python main.py
```

Query via the A2A protocol on port 10000.

### Option 2: CLI Chat

```bash
python main.py --chat
```

### Option 3: Chat UI (Recommended)

A ChatGPT-like web interface powered by CopilotKit + AG-UI protocol.

**Start the AG-UI backend (port 8000):**
```bash
uvicorn agui_server:app --port 8000
```

**Start the frontend (port 3000):**
```bash
cd chat-ui
npm run dev
```

Open http://localhost:3000 and start chatting.

### Example Queries

- "Analyze Nvidia for me" — resolves ticker, pulls financials, generates recommendation
- "Should I invest in real estate or pay down my mortgage?" — evaluates housing market + career trajectory
- "Compare getting a GCP cert vs investing $5k in gold" — cross-category analysis

## Evaluation

The system ships with a reproducible evaluation suite ([`tests/eval/`](tests/eval/))
that scores the agent on two independent dimensions for every case in a
[golden dataset](tests/eval/golden_dataset.json):

- **Routing / trajectory correctness** (deterministic) — verifies the root agent
  delegated to the right sub-agents (e.g. `ticker_resolver → research_agent →
  analyst_agent`), captured from the run's tool-call events.
- **Response quality** (LLM-as-judge) — an independent Gemini judge grades each
  final answer against a per-case rubric, including a responsible-AI check (no
  guaranteed-return claims) and a personalization check (uses the investor's
  profile).

```bash
python tests/eval/run_eval.py            # full suite
python tests/eval/run_eval.py --no-judge # routing checks only (no API cost)
```

Evaluation runs against the synthetic `investor_profile.example.md` only. See the
[evaluation README](tests/eval/README.md) for methodology and the report format.

## Project Structure

```
├── main.py                      # A2A service entry point and root agent
├── agui_server.py               # AG-UI backend for CopilotKit frontend
├── ticker_resolver.py           # Ticker symbol resolution agent
├── research_agent.py            # Financial data research via Alpha Vantage
├── analyst_agent.py             # Analysis and recommendation agent
├── alternatives_agent.py        # Alternative investment evaluation
├── self_investment_agent.py     # Career/human capital optimization
├── financial_ai_v2/             # ADK Workbench package
│   ├── __init__.py
│   └── agent.py
├── chat-ui/                     # Next.js frontend (CopilotKit + AG-UI)
│   ├── src/app/                 # App router pages and API routes
│   ├── src/components/          # AgentSelector sidebar
│   ├── Dockerfile.frontend      # Frontend container for Cloud Run
│   └── .env.local               # ADK_AGENT_URL config
├── Dockerfile.backend           # Backend container for Cloud Run
├── investor_profile.example.md  # Template — copy to investor_profile.md
├── .env.example                 # Template — copy to .env
├── requirements.txt             # Python dependencies
└── README.md
```

## Cloud Run Deployment

### Backend (internal only)

```bash
# Store API keys in Secret Manager (one-time)
echo -n "YOUR_KEY" | gcloud secrets create GOOGLE_API_KEY --data-file=-
# Repeat for ALPHA_VANTAGE_API_KEY, FRED_API_KEY, BLS_API_KEY, ONET_API_KEY

# Deploy
gcloud run deploy financial-ai-backend \
  --source=. \
  --dockerfile=Dockerfile.backend \
  --no-allow-unauthenticated \
  --ingress=internal \
  --set-secrets="GOOGLE_API_KEY=GOOGLE_API_KEY:latest,\
ALPHA_VANTAGE_API_KEY=ALPHA_VANTAGE_API_KEY:latest,\
FRED_API_KEY=FRED_API_KEY:latest,\
BLS_API_KEY=BLS_API_KEY:latest,\
ONET_API_KEY=ONET_API_KEY:latest" \
  --memory=1Gi \
  --region=us-central1
```

### Frontend

```bash
BACKEND_URL=$(gcloud run services describe financial-ai-backend \
  --region=us-central1 --format='value(status.url)')

gcloud run deploy financial-ai-frontend \
  --source=chat-ui/ \
  --dockerfile=chat-ui/Dockerfile.frontend \
  --allow-unauthenticated \
  --set-env-vars="ADK_AGENT_URL=${BACKEND_URL}" \
  --memory=512Mi \
  --region=us-central1
```

### IAP (Gmail-only access)

1. Create a Global External Application Load Balancer for the frontend service
2. Enable IAP on the load balancer backend:
   ```bash
   gcloud iap web enable --resource-type=backend-services \
     --oauth2-client-id=<CLIENT_ID> \
     --oauth2-client-secret=<CLIENT_SECRET>
   ```
3. Grant only your Gmail access:
   ```bash
   gcloud iap web add-iam-policy-binding \
     --resource-type=backend-services \
     --member="user:YOUR_GMAIL@gmail.com" \
     --role="roles/iap.httpsResourceAccessUser"
   ```
4. Grant frontend → backend service-to-service auth:
   ```bash
   FRONTEND_SA=$(gcloud run services describe financial-ai-frontend \
     --region=us-central1 --format='value(spec.template.spec.serviceAccountName)')
   gcloud run services add-iam-policy-binding financial-ai-backend \
     --region=us-central1 \
     --member="serviceAccount:${FRONTEND_SA}" \
     --role="roles/run.invoker"
   ```

## License

MIT
