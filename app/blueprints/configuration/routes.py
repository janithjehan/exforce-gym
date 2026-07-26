from datetime import datetime
from flask import render_template, redirect, url_for, flash
from flask_login import current_user

from app.blueprints.configuration import configuration_bp
from app.blueprints.configuration.forms import ConfigurationForm
from app.extensions import db
from app.models.configuration import AppConfiguration
from app.utils.decorators import admin_required


@configuration_bp.route('/', methods=['GET', 'POST'])
@admin_required
def edit_configuration():
    settings = AppConfiguration.get()
    form = ConfigurationForm(obj=settings)

    if form.validate_on_submit():
        settings.bank_transfer_details = form.bank_transfer_details.data.strip() or None
        settings.updated_by_id = current_user.id
        settings.updated_at = datetime.utcnow()
        db.session.commit()
        flash('Configuration updated.', 'success')
        return redirect(url_for('configuration.edit_configuration'))

    return render_template(
        'configuration/edit.html', form=form, settings=settings, title='Configuration'
    )