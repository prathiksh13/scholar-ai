import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", BASE_DIR / "storage" / "uploads"))
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", BASE_DIR / "storage" / "outputs"))
GENERATED_DIR = Path(os.getenv("GENERATED_DIR", BASE_DIR / "generated"))
TEX_DIR = GENERATED_DIR / "tex"
IMAGE_DIR = GENERATED_DIR / "images"
PDF_DIR = GENERATED_DIR / "pdf"

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
TEX_DIR.mkdir(parents=True, exist_ok=True)
IMAGE_DIR.mkdir(parents=True, exist_ok=True)
PDF_DIR.mkdir(parents=True, exist_ok=True)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
FIREBASE_PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID", "")
FIREBASE_CREDENTIALS_PATH = os.getenv("FIREBASE_CREDENTIALS_PATH", "")
SKIP_AUTH = os.getenv("SKIP_AUTH", "false").lower() == "true"

SUPPORTED_FORMATS = ["IEEE", "ACM", "Springer", "APA", "MLA"]
