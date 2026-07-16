from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_bcrypt import Bcrypt
from flask_wtf.csrf import CSRFProtect

db = SQLAlchemy()
login_manager = LoginManager()
bcrypt = Bcrypt()
csrf = CSRFProtect()

login_manager.login_view = 'auth.login'
login_manager.login_message = 'Please log in to access this page.'
login_manager.login_message_category = 'warning'


@login_manager.user_loader
def load_user(user_id):
    """
        Reload a user from the database using the user_id stored in the session.
        Returns None if the user is deactivated or archived, effectively logging them out.
    """
    from app.models.user import User

    user = User.query.get(int(user_id))
    if user and (not user.is_active or user.is_archived):
        return None
    return user
