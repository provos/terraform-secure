import os
import sys
from pathlib import Path

# Get the absolute path to the project root
project_root = Path(__file__).parent.parent

# Add the src directory to Python path
src_path = project_root / "src"
sys.path.insert(0, str(src_path))
