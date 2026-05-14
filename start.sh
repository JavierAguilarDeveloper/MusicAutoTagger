#!/bin/bash
set -e

DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

# Create venv if it doesn't exist
if [ ! -d ".venv" ]; then
  echo "Creando entorno virtual..."
  python3 -m venv .venv
fi

source .venv/bin/activate

# Install/upgrade dependencies
echo "Instalando dependencias..."
pip install -q -r requirements.txt

echo ""
echo "==============================="
echo "  Music Auto Tagger"
echo "  http://localhost:8000"
echo "==============================="
echo ""

uvicorn main:app --host 0.0.0.0 --port 8000
