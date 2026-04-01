#!/bin/bash
# Start both MCP servers

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Activate virtual environment if it exists
if [ -d "$SCRIPT_DIR/venv" ]; then
    source "$SCRIPT_DIR/venv/bin/activate"
elif [ -d "$SCRIPT_DIR/../agent-venv" ]; then
    source "$SCRIPT_DIR/../agent-venv/bin/activate"
fi

# Start tools server in background
echo "Starting tools-server on port 5050..."
cd "$SCRIPT_DIR/tools-server"
python mcp_retail_server.py --port 5050 &
TOOLS_PID=$!

# Wait for tools server to start
sleep 2

# Start sandbox server
echo "Starting sandbox-server on port 5051..."
cd "$SCRIPT_DIR/sandbox-server"
python mcp_server.py --port 5051 --tools-url http://localhost:5050/sse &
SANDBOX_PID=$!

echo ""
echo "Both servers started:"
echo "  - tools-server:   http://localhost:5050/sse (PID: $TOOLS_PID)"
echo "  - sandbox-server: http://localhost:5051/sse (PID: $SANDBOX_PID)"
echo ""
echo "Press Ctrl+C to stop both servers"

# Wait for interrupt
trap "kill $TOOLS_PID $SANDBOX_PID 2>/dev/null; exit" INT TERM
wait
