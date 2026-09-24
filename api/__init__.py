from pathlib import Path
import sys

# Ensure cozyhome_ai_poc_v2 is in sys.path
POC_DIR = Path(__file__).resolve().parent.parent.parent / "cozyhome_ai_poc_v2"
if str(POC_DIR) not in sys.path:
    sys.path.insert(0, str(POC_DIR))
