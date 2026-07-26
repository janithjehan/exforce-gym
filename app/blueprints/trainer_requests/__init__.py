from flask import Blueprint

trainer_requests_bp = Blueprint('trainer_requests', __name__)

from app.blueprints.trainer_requests import routes  # noqa: E402,F401
