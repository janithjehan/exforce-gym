from datetime import datetime
from app.extensions import db


class Attendance(db.Model):
    __tablename__ = 'attendances'

    id = db.Column(db.Integer, primary_key=True)
    member_id = db.Column(db.Integer, db.ForeignKey('members.id'), nullable=False)
    check_in = db.Column(db.DateTime, nullable=False)
    check_out = db.Column(db.DateTime, nullable=True)
    notes = db.Column(db.Text, nullable=True)

    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    updated_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    member = db.relationship(
        'Member', foreign_keys=[member_id],
        backref=db.backref('attendances', lazy='dynamic',
                           order_by='Attendance.check_in.desc()')
    )
    created_by = db.relationship('User', foreign_keys=[created_by_id])
    updated_by = db.relationship('User', foreign_keys=[updated_by_id])

    @property
    def is_checked_out(self):
        return self.check_out is not None

    @property
    def duration_minutes(self):
        if not self.check_out:
            return None
        return int((self.check_out - self.check_in).total_seconds() // 60)

    @property
    def duration_label(self):
        mins = self.duration_minutes
        if mins is None:
            return '—'
        h, m = divmod(mins, 60)
        if h:
            return f'{h}h {m}m' if m else f'{h}h'
        return f'{m}m'

    @property
    def check_in_date(self):
        return self.check_in.date()

    def __repr__(self):
        return f'<Attendance member={self.member_id} in={self.check_in}>'
