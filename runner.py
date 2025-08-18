import threading
import subprocess
import sys
import os
import time

def run_streamlit():
    """
    Launch the Streamlit app as a subprocess.
    """
    streamlit_path = os.path.join(os.path.dirname(__file__), "streamlit_app.py")
    # Use sys.executable to ensure the same Python environment
    cmd = [sys.executable, "-m", "streamlit", "run", streamlit_path]
    # Inherit environment variables
    env = os.environ.copy()
    # Streamlit will block, so run as subprocess
    process = subprocess.Popen(cmd, env=env)
    return process

def run_bot():
    """
    Launch the WhatsApp bot (main.py) in the current process/thread.
    """
    import cctv.main
    cctv.main.main()

def main():
    print("Starting CCTV Swine System: Streamlit app and WhatsApp bot...")

    # Start Streamlit app in a separate thread (as subprocess)
    streamlit_thread = threading.Thread(target=run_streamlit, daemon=True)
    streamlit_thread.start()
    print("Streamlit app launched.")

    # Start WhatsApp bot in main thread (blocking)
    try:
        run_bot()
    except KeyboardInterrupt:
        print("Shutting down...")
    finally:
        print("CCTV Swine System stopped.")

if __name__ == "__main__":
    main()
