from flask import Blueprint

packages_bp = Blueprint('packages', __name__, template_folder='templates')

from app.blueprints.packages import routes
