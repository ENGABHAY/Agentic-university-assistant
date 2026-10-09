"""Usage: python -m scripts.ingest [folder]   (default: data/raw; supports .pdf and .txt)"""
import sys
from pathlib import Path
from app.rag import ingest

folder = Path(sys.argv[1] if len(sys.argv) > 1 else "data/raw")
for f in sorted(folder.iterdir()):
    if f.suffix.lower() in {".pdf", ".txt"}:
        print(f.name, "->", ingest(str(f)), "chunks")
