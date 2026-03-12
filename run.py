"""
Titan-Credit Launch Script — Start both FastAPI + Streamlit.
Usage:  python run.py
"""
import subprocess
import sys
import time


def main():
    print("=" * 60)
    print("  TITAN-CREDIT Decisioning Engine v1.0.0")
    print("  Hierarchical Swarm with Reflexion Architecture")
    print("=" * 60)
    print()
    print("Starting services...")

    # Start FastAPI in background
    api_proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "src.api.main:app",
         "--host", "0.0.0.0", "--port", "8000", "--reload"],
        cwd=".",
    )
    print("[API]       http://localhost:8000")
    print("[API Docs]  http://localhost:8000/docs")

    time.sleep(2)

    # Start Streamlit
    dash_proc = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", "dashboard/app.py",
         "--server.port", "8501", "--server.headless", "true"],
        cwd=".",
    )
    print("[Dashboard] http://localhost:8501")
    print()
    print("Press Ctrl+C to stop all services.")

    try:
        api_proc.wait()
    except KeyboardInterrupt:
        print("\nShutting down...")
        api_proc.terminate()
        dash_proc.terminate()
        api_proc.wait()
        dash_proc.wait()
        print("Stopped.")


if __name__ == "__main__":
    main()
