"""equipment categories configurable via configuration

Equipment.category moves from a fixed Postgres enum to free text validated
against AppConfiguration.equipment_categories (a comma-separated menu edited
on the new Configuration > Equipment Categories page), mirroring how
Package.installment_options already works against AppConfiguration.
installment_options. Existing rows are translated from their old enum member
name (e.g. 'STRENGTH_MACHINE') to the equivalent display label (e.g.
'Strength Machine') so they read the same as before the change, and that
same label list seeds the new configurable menu.

Revision ID: 2f5648d844c2
Revises: d4bb72d44783
Create Date: 2026-08-03 19:59:23.417350

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '2f5648d844c2'
down_revision = 'd4bb72d44783'
branch_labels = None
depends_on = None

DEFAULT_CATEGORY_LIST = 'Cardio,Strength Machine,Free Weights,Functional Training,Accessories,Other'

CATEGORY_LABELS = {
    'CARDIO': 'Cardio',
    'STRENGTH_MACHINE': 'Strength Machine',
    'FREE_WEIGHTS': 'Free Weights',
    'FUNCTIONAL': 'Functional Training',
    'ACCESSORIES': 'Accessories',
    'OTHER': 'Other',
}


def upgrade():
    op.add_column(
        'app_configuration',
        sa.Column('equipment_categories', sa.String(length=500), nullable=True),
    )
    op.execute(
        f"UPDATE app_configuration SET equipment_categories = '{DEFAULT_CATEGORY_LIST}'"
    )

    # Enum -> varchar requires an explicit USING cast in Postgres; autogenerate's
    # plain alter_column can't express that, so this part is hand-written.
    op.execute('ALTER TABLE equipments ALTER COLUMN category TYPE VARCHAR(100) USING category::text')
    for enum_name, label in CATEGORY_LABELS.items():
        op.execute(f"UPDATE equipments SET category = '{label}' WHERE category = '{enum_name}'")
    op.execute('DROP TYPE IF EXISTS equipmentcategory')


def downgrade():
    op.execute(
        "CREATE TYPE equipmentcategory AS ENUM "
        "('CARDIO', 'STRENGTH_MACHINE', 'FREE_WEIGHTS', 'FUNCTIONAL', 'ACCESSORIES', 'OTHER')"
    )
    for enum_name, label in CATEGORY_LABELS.items():
        op.execute(f"UPDATE equipments SET category = '{enum_name}' WHERE category = '{label}'")
    op.execute(
        "ALTER TABLE equipments ALTER COLUMN category TYPE equipmentcategory "
        "USING category::equipmentcategory"
    )

    op.drop_column('app_configuration', 'equipment_categories')
