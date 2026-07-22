from flask import Blueprint

equipment_bp = Blueprint('equipment', __name__, template_folder='templates')

from app.blueprints.equipment import routes  # noqa: E402, F401