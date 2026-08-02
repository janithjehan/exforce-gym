"""baseline - existing schema, no-op

Marks the point where Flask-Migrate/Alembic was adopted into this project.
The live DB already matched every current model exactly (built up over time
via db.create_all() plus manual ALTER TABLE/ALTER TYPE statements, documented
in CLAUDE.md) — confirmed by `flask db migrate` reporting "No changes in
schema detected." This revision is intentionally a no-op; it exists only so
`flask db stamp head` has something to record as the DB's starting point.
Every schema change from here forward should be a real migration.

Revision ID: d4bb72d44783
Revises:
Create Date: 2026-08-03 01:49:05.948017

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd4bb72d44783'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
