#!/bin/bash
# Install dependencies if missing (basic check)
if ! python3 -c "import fastapi" &> /dev/null; then
    echo "Detail: fastapi not found. Installing..."
    pip install fastapi uvicorn
fi

echo "Starting Lunch Bot Server..."

while true; do
    echo "[$(date)] Starting bot_server.py..."
    python3 bot_server.py
    
    echo ""
    echo "[$(date)] Server stopped. Restarting in 5 seconds..."
    echo "Press CTRL+C to stop the loop."
    sleep 5
done
