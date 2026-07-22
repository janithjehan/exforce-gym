from flask import Blueprint

schedules_bp = Blueprint('schedules', __name__, template_folder='templates')

from app.blueprints.schedules import routes  # noqa: E402, F401