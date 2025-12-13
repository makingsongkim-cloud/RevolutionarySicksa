#!/bin/bash
# Install dependencies if missing (basic check)
if ! python3 -c "import fastapi" &> /dev/null; then
    echo "Detail: fastapi not found. Installing..."
    pip install fastapi uvicorn
fi

echo "Starting Lunch Bot Server..."
python3 bot_server.py
