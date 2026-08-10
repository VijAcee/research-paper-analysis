import sys
import os

# Append the absolute path of 'app' directory to Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'app')))

import uvicorn

if __name__ == "__main__":
    print("Starting PaperLens FastAPI Backend...")
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
