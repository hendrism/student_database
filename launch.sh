#!/bin/bash
# Student Database Launcher for macOS

cd "/Users/Sean-Work/Databases/student_database"
source "/Users/Sean-Work/Databases/student_database/venv/bin/activate"

echo "🏥 Starting Student Database..."
echo "📍 Access at: http://127.0.0.1:5000"
echo "⏹️  Press Ctrl+C to stop"
echo ""

export FLASK_ENV=development
export FLASK_APP=app.py

"/Users/Sean-Work/Databases/student_database/venv/bin/python" app.py
