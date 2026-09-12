"""SwachhLens backend launcher."""
import os
import uvicorn
from dotenv import load_dotenv

if __name__ == "__main__":
    load_dotenv()
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    reload = os.getenv("RELOAD", "0") == "1"
    print(f"Starting SwachLens API on {host}:{port}")
    uvicorn.run("app.main:app", host=host, port=port, reload=reload)
