"""Environment loading helpers."""
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def load_project_env() -> None:
    """Load the project .env regardless of the current working directory."""
    load_dotenv(PROJECT_ROOT / ".env")
