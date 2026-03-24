import sys
import os

# Add parent directory so we can import our modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"), override=True)

from main import create_root_agent

root_agent = create_root_agent()
