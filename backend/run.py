import os
from pathlib import Path

from dotenv import load_dotenv
import uvicorn


load_dotenv(Path(__file__).with_name(".env"))

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=os.getenv("APP_HOST", "127.0.0.1"),
        port=int(os.getenv("APP_PORT", "8001")),
        reload=os.getenv("APP_ENV", "development").lower() != "production",
    )
