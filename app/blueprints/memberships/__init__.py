from flask import Blueprint

memberships_bp = Blueprint('memberships', __name__, template_folder='templates')

from app.blueprints.memberships import routes  # noqa: E402, F401
