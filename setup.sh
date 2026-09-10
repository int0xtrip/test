#!/bin/bash
set -e

echo "==============================="
echo " Oculometry - Setup"
echo "==============================="
echo ""

# Backend setup
echo "[1/2] Setting up backend..."
cd backend

if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
source venv/bin/activate
pip install -r requirements.txt
echo "Backend ready."

cd ..

# Frontend setup
echo ""
echo "[2/2] Setting up frontend..."
cd frontend
npm install
echo "Frontend ready."

cd ..

echo ""
echo "==============================="
echo " Setup complete!"
echo "==============================="
echo ""
echo " To run:"
echo "   Terminal 1: cd backend && source venv/bin/activate && python run.py"
echo "   Terminal 2: cd frontend && npm run dev"
echo ""
echo " Then open http://localhost:3000"
echo ""
