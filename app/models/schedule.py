import enum
from datetime import datetime, date
from app.extensions import db


class ScheduleStatus(enum.Enum):
    PLANNED = 'planned'
    COMPLETED = 'completed'
    CANCELLED = 'cancelled'

    @property
    def label(self):
        return self.value.capitalize()

    @property
    def badge_class(self):
        return {
            'planned': 'primary',
            'completed': 'success',
            'cancelled': 'secondary',
        }[self.value]


class Schedule(db.Model):
    """Workout plan a trainer assigns to a member over a date range (SRS 3.9)."""
    __tablename__ = 'schedules'

    id = db.Column(db.Integer, primary_key=True)
    member_id = db.Column(db.Integer, db.ForeignKey('members.id'), nullable=False)
    trainer_id = db.Column(db.Integer, db.ForeignKey('trainers.id'), nullable=False)

    title = db.Column(db.String(150), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)

    status = db.Column(
        db.Enum(ScheduleStatus), nullable=False, default=ScheduleStatus.PLANNED
    )
    notes = db.Column(db.Text, nullable=True)

    # FR-SCH-02: bumped on every edit; ScheduleEditLog keeps the trail
    version = db.Column(db.Integer, nullable=False, default=1)

    # Audit
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    updated_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    member = db.relationship(
        'Member', foreign_keys=[member_id],
        backref=db.backref('schedules', lazy='dynamic', order_by='Schedule.start_date.desc()'),
    )
    trainer = db.relationship(
        'Trainer', foreign_keys=[trainer_id],
        backref=db.backref('schedules', lazy='dynamic', order_by='Schedule.start_date.desc()'),
    )
    created_by = db.relationship('User', foreign_keys=[created_by_id])
    updated_by = db.relationship('User', foreign_keys=[updated_by_id])

    items = db.relationship(
        'ScheduleItem', backref='schedule', lazy='joined',
        order_by='ScheduleItem.sort_order.asc()',
        cascade='all, delete-orphan',
    )
    edit_logs = db.relationship(
        'ScheduleEditLog', backref='schedule', lazy='dynamic',
        order_by='ScheduleEditLog.created_at.desc()',
    )

    @property
    def is_current(self):
        return (
            self.status == ScheduleStatus.PLANNED
            and self.start_date <= date.today() <= self.end_date
        )

    @property
    def date_range_label(self):
        return f"{self.start_date.strftime('%d %b %Y')} – {self.end_date.strftime('%d %b %Y')}"

    def __repr__(self):
        return f'<Schedule {self.id} "{self.title}" member={self.member_id} v{self.version}>'


class ScheduleItem(db.Model):
    """One workout line in a schedule — FR-SCH-01: workout + sets/reps/rest."""
    __tablename__ = 'schedule_items'

    id = db.Column(db.Integer, primary_key=True)
    schedule_id = db.Column(db.Integer, db.ForeignKey('schedules.id'), nullable=False)
    workout_id = db.Column(db.Integer, db.ForeignKey('workouts.id'), nullable=False)

    day_label = db.Column(db.String(30), nullable=False)  # e.g. "Monday", "Day 1"
    sets = db.Column(db.Integer, nullable=False)
    reps = db.Column(db.String(20), nullable=False)  # "12" or a range like "8-12"
    rest_seconds = db.Column(db.Integer, nullable=False, default=60)
    notes = db.Column(db.String(200), nullable=True)
    sort_order = db.Column(db.Integer, nullable=False, default=0)

    workout = db.relationship('Workout', foreign_keys=[workout_id])

    @property
    def rest_label(self):
        if self.rest_seconds >= 60 and self.rest_seconds % 60 == 0:
            return f'{self.rest_seconds // 60} min'
        return f'{self.rest_seconds} sec'

    def __repr__(self):
        return f'<ScheduleItem s={self.schedule_id} w={self.workout_id} {self.sets}x{self.reps}>'


class ScheduleEditLog(db.Model):
    """FR-SCH-02: one row per schedule edit — who, when, which version, what changed."""
    __tablename__ = 'schedule_edit_logs'

    id = db.Column(db.Integer, primary_key=True)
    schedule_id = db.Column(db.Integer, db.ForeignKey('schedules.id'), nullable=False)
    edited_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    version = db.Column(db.Integer, nullable=False)  # version created by this edit
    summary = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    edited_by = db.relationship('User', foreign_keys=[edited_by_id])

    def __repr__(self):
        return f'<ScheduleEditLog s={self.schedule_id} v{self.version}>'