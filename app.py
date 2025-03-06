from flask import Flask
from routes import routes_bp
from models import db, Student, Session, Goal, Objective, session_objectives_association
# No Flask-Migrate import here for now

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'your_secret_key'

db.init_app(app)

app.register_blueprint(routes_bp, app=app, db=db)

with app.app_context():
    print("--- Before db.create_all() ---")  # ADD THIS PRINT STATEMENT BEFORE
    db.create_all()
    print("--- After db.create_all() ---")   # ADD THIS PRINT STATEMENT AFTER

if __name__ == '__main__':
    app.run(debug=True)