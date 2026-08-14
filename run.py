import os
import sys
import uvicorn

# Add project root to sys.path so imports work cleanly from anywhere
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app.core.config import settings

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    )
