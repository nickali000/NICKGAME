#!/bin/bash

# Kill existing servers
echo "Stopping servers..."
pkill -f "python3 python-server/app.py"
pkill -f "go-server/main"

# Wait a bit
sleep 1

# Build Go Server
echo "Building Go Server..."
cd go-server
go build -o main .
cd ..

# Start Python Server
echo "Starting Python Server on port 5001..."
/usr/bin/python3 python-server/app.py > python.log 2>&1 &
PYTHON_PID=$!

# Start Go Server
echo "Starting Go Server on port 8080..."
./go-server/main > go.log 2>&1 &
GO_PID=$!

echo "Servers restarted!"
echo "Python PID: $PYTHON_PID"
echo "Go PID: $GO_PID"
echo "Access at http://localhost:8080"
