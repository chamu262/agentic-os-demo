"""One-command start: python run.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from agentic_os.server import main  # noqa: E402

main()
