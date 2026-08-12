from fastapi import FastAPI
from dotenv import load_dotenv
import os

load_dotenv()

app = FastAPI(title="PRISM")

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")


@app.get("/health")
def health():
    return {
        "status": "ok",
        "key_loaded": OPENROUTER_API_KEY is not None,
    }
