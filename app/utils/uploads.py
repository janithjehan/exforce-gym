"""Shared image-upload helper — reads an upload into DB-storable bytes.

Images (avatars, equipment, ...) are stored as binary data directly on their
owning row, not on the filesystem, so they survive redeploys on hosts with no
persistent disk.
"""
import mimetypes

from werkzeug.utils import secure_filename

ALLOWED_IMAGE_EXTENSIONS = ['jpg', 'jpeg', 'png', 'gif', 'webp']


def read_image_bytes(file_storage):
    """Read an uploaded image into (data, mimetype) for storage as a DB blob."""
    original = secure_filename(file_storage.filename or '')
    ext = original.rsplit('.', 1)[-1].lower() if '.' in original else 'jpg'
    mimetype = file_storage.mimetype or mimetypes.guess_type(original)[0] or f'image/{ext}'
    return file_storage.read(), mimetype
