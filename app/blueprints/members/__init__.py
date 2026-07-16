from flask import Blueprint

members_bp = Blueprint('members', __name__, template_folder='templates')

from app.blueprints.members import routes  # noqa: E402, F401
