"""AG-UI server wrapping the ADK financial root agent for CopilotKit frontend."""

import os
import logging
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"), override=True)
if os.getenv("GOOGLE_API_KEY"):
    os.environ["GOOGLE_API_KEY"] = os.getenv("GOOGLE_API_KEY")

# Enable AG-UI middleware logging to see event translation
logging.basicConfig(level=logging.INFO)
logging.getLogger("ag_ui_adk").setLevel(logging.DEBUG)

from main import create_root_agent
from ag_ui_adk import ADKAgent, add_adk_fastapi_endpoint
from google.adk.agents.run_config import RunConfig, StreamingMode
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

agent = create_root_agent()


def _run_config(input):
    return RunConfig(streaming_mode=StreamingMode.NONE)


adk_agent = ADKAgent(
    adk_agent=agent,
    app_name="fin_app",
    user_id="user_1",
    session_timeout_seconds=3600,
    run_config_factory=_run_config,
)

app = FastAPI(title="Financial AI AG-UI Server")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
add_adk_fastapi_endpoint(app, adk_agent, path="/")

if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
