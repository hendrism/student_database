from flask import Flask
from routes import routes_bp
from models import db

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////Users/Sean-Work/Databases/student_database/database.db'  # YOUR ABSOLUTE PATH
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'your_secret_key'

db.init_app(app)
app.register_blueprint(routes_bp)

with app.app_context():
    db.create_all()
    print("--- Database tables created (or already exist) ---")

if __name__ == '__main__':
    app.run(debug=True)