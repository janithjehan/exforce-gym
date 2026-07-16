from flask import Blueprint

trainers_bp = Blueprint('trainers', __name__)

from app.blueprints.trainers import routes  # noqa: F401, E402
