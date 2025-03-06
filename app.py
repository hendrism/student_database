from flask import Flask
from models import db, Student, Session, Goal, Objective, session_objectives_association
from routes import routes_bp
from flask_migrate import Migrate  # Import Migrate
from datetime import datetime

app = Flask(__name__)

app.jinja_env.filters['strftime'] = datetime.strftime  # Register strftime as a Jinja filter - ADD THIS LINE HERE

# Database Configuration - SQLite (adjust path if needed)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////Users/Sean-Work/Databases/student_database/database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False  # Disable modification tracking

# Initialize SQLAlchemy with the app
db.init_app(app)

# Initialize Flask-Migrate with the app and database
migrate = Migrate(app, db)

# Register the routes blueprint
app.register_blueprint(routes_bp)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # Create database tables if they don't exist (for initial setup, not migrations)
    app.run(debug=True)