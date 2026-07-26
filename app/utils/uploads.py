"""Shared image-upload helpers for static uploads (avatars, equipment, ...).

Files are stored under app/static/uploads/<subdir>/ with a unique uuid name,
so `url_for('static', filename='uploads/<subdir>/<name>')` serves them.
Deletion is best-effort — filesystem errors never block a request.
"""
import os
import uuid

from flask import current_app
from werkzeug.utils import secure_filename

ALLOWED_IMAGE_EXTENSIONS = ['jpg', 'jpeg', 'png', 'gif', 'webp']


def _dir(subdir):
    path = os.path.join(current_app.static_folder, 'uploads', subdir)
    os.makedirs(path, exist_ok=True)
    return path


def save_image(file_storage, subdir):
    """Store an uploaded image under uploads/<subdir>/; return the stored filename."""
    original = secure_filename(file_storage.filename or '')
    ext = original.rsplit('.', 1)[-1].lower() if '.' in original else 'jpg'
    filename = f'{uuid.uuid4().hex}.{ext}'
    file_storage.save(os.path.join(_dir(subdir), filename))
    return filename


def delete_image(filename, subdir):
    """Best-effort delete of uploads/<subdir>/<filename> — never raises."""
    if not filename:
        return
    path = os.path.join(_dir(subdir), filename)
    try:
        if os.path.isfile(path):
            os.remove(path)
    except OSError:
        pass
