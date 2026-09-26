from pathlib import Path
import multiprocessing
import uvicorn

ROOT = Path(__file__).resolve().parent

def main():
    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        app_dir=str(ROOT / "backend"),
    )

if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
