from flask import Blueprint

workouts_bp = Blueprint('workouts', __name__, template_folder='templates')

from app.blueprints.workouts import routes  # noqa: E402, F401