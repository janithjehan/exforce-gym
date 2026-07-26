from flask import Blueprint

expenses_bp = Blueprint('expenses', __name__, template_folder='templates')

from app.blueprints.expenses import routes
