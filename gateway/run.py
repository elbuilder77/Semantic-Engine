import os
import sys
import uvicorn

# Inject parent directory to path so 'ses' library is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

if __name__ == "__main__":
    print("==========================================================")
    print("[SES] Enterprise Gateway Server starting...")
    print("[WEB] Dashboard: http://localhost:8000")
    print("[KEY] Default Admin Key: ses_dev_secret_key")
    print("==========================================================")
    
    # Run server
    uvicorn.run("gateway.server:app", host="127.0.0.1", port=8000, reload=False)
