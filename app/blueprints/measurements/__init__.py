from flask import Blueprint

measurements_bp = Blueprint('measurements', __name__)

from app.blueprints.measurements import routes  # noqa: F401, E402