"""Flask application entry point for the Student Database app."""

from flask import Flask, request
from routes import routes_bp
from models import db
from flask_migrate import Migrate

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////Users/Sean-Work/Databases/student_database/database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'your_secret_key'
app.config['DEBUG'] = True

db.init_app(app)
migrate = Migrate(app, db)
app.register_blueprint(routes_bp)

@app.errorhandler(404)
def log_404(e):
    print(f"❗️ 404 for {request.method} {request.path!r}")
    return e, 404

if __name__ == '__main__':
    app.run(debug=True)