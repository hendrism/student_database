#!/bin/bash

cd "/Users/Sean-Work/Databases/student_database"
source venv/bin/activate
export FLASK_APP=app.py
export FLASK_ENV=development
sleep 1
open http://localhost:5000
flask run