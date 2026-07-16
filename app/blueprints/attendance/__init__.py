from flask import Blueprint

attendance_bp = Blueprint('attendance', __name__)

from app.blueprints.attendance import routes  # noqa: F401, E402
