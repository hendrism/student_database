from flask import Blueprint

routes_bp = Blueprint('routes', __name__)

# Import route modules so they register routes on the blueprint
from . import main, students, soap, reports, activities

__all__ = ['routes_bp']

@routes_bp.app_context_processor
def inject_current_date():
    from datetime import date
    return {'current_date': date.today().isoformat()}
