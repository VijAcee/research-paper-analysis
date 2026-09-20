import sys
import os
import uvicorn

# Append the absolute path of 'app' directory to Python path
app_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), 'app'))
backend_dir = os.path.abspath(os.path.dirname(__file__))

sys.path.append(app_dir)

if __name__ == "__main__":
    print("Starting PaperLens FastAPI Backend (Scoped File Watcher)...")
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_dirs=[app_dir],
        reload_excludes=["*.pyc", "*.log", "scratch/*", "frontend/*", ".git/*", "chroma_db/*", "tests/*"]
    )
