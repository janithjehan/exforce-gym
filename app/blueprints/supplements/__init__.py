from flask import Blueprint

supplements_bp = Blueprint('supplements', __name__, template_folder='templates')

from app.blueprints.supplements import routes  # noqa: E402, F401