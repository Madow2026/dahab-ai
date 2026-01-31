"""
Run All Script - Launches both Worker and Streamlit UI
"""

import subprocess
import sys
import os
import time
import signal

def main():
    """Launch worker and streamlit processes"""
    print("🚀 Starting DAHAB AI Platform")
    print("=" * 60)
    
    worker_process = None
    streamlit_process = None
    
    try:
        # Start worker process
        print("\n📊 Starting automated worker process...")
        worker_process = subprocess.Popen(
            [sys.executable, "worker.py"],
            creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == 'win32' else 0
        )
        time.sleep(2)  # Give worker time to start
        
        # Start Streamlit UI
        print("🌐 Starting Streamlit dashboard...")
        streamlit_process = subprocess.Popen(
            [sys.executable, "-m", "streamlit", "run", "app.py"],
            creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == 'win32' else 0
        )
        
        print("\n" + "=" * 60)
        print("✅ Both processes started successfully!")
        print("=" * 60)
        print("\n📋 Running processes:")
        print(f"   • Worker: PID {worker_process.pid}")
        print(f"   • Streamlit: PID {streamlit_process.pid}")
        print("\n🌐 Dashboard URL: http://localhost:8501")
        print("\n⚠️  To stop: Close this window or press Ctrl+C")
        print("=" * 60)
        
        # Keep script running
        while True:
            # Check if processes are still alive
            if worker_process.poll() is not None:
                print("\n❌ Worker process died. Restarting...")
                worker_process = subprocess.Popen(
                    [sys.executable, "worker.py"],
                    creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == 'win32' else 0
                )
            
            if streamlit_process.poll() is not None:
                print("\n❌ Streamlit process died. Restarting...")
                streamlit_process = subprocess.Popen(
                    [sys.executable, "-m", "streamlit", "run", "app.py"],
                    creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == 'win32' else 0
                )
            
            time.sleep(5)
    
    except KeyboardInterrupt:
        print("\n\n🛑 Shutdown requested...")
    
    finally:
        # Cleanup
        print("\n🧹 Cleaning up processes...")
        
        if worker_process and worker_process.poll() is None:
            print("   Stopping worker...")
            worker_process.terminate()
            worker_process.wait(timeout=5)
        
        if streamlit_process and streamlit_process.poll() is None:
            print("   Stopping Streamlit...")
            streamlit_process.terminate()
            streamlit_process.wait(timeout=5)
        
        print("✅ Shutdown complete")


if __name__ == "__main__":
    main()
