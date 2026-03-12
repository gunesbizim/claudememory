#!/usr/bin/env python3
# Shim for backwards compatibility — real implementation lives in claude_memory_mcp_server.py
import runpy, sys
from pathlib import Path
sys.exit(runpy.run_path(str(Path(__file__).parent / "claude_memory_mcp_server.py"), run_name="__main__"))
