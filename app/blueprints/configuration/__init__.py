from flask import Blueprint

configuration_bp = Blueprint('configuration', __name__, template_folder='templates')

from app.blueprints.configuration import routes