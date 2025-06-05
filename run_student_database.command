#!/bin/bash

cd "/Users/Sean-Work/Databases/student_database"
source venv/bin/activate
export FLASK_APP=app.py
export FLASK_ENV=development
flask run