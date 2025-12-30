#!/bin/bash

# Kill any existing instances
pkill -f "python-server/app.py"
pkill -f "modular-platform"

# Start Python Server
echo "Starting Python Server on port 5001..."
./venv/bin/python python-server/app.py > python_server.log 2>&1 &
PYTHON_PID=$!

# Wait for Python to start
sleep 2

# Start Go Server
echo "Starting Go Server on port 8080..."
./go-server/modular-platform > go_server.log 2>&1 &
GO_PID=$!

echo "Servers started!"
echo "Python PID: $PYTHON_PID"
echo "Go PID: $GO_PID"
echo "Access at http://localhost:8080"
