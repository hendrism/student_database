"""Blueprint package for application routes organized by feature."""

from flask import Blueprint

# Shared blueprint used across route modules
routes_bp = Blueprint('routes', __name__)

# Import modules that define routes to register them with the blueprint
from . import main, students, sessions, trial_logs, soap, reports, activities
