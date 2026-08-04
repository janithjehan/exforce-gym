"""equipment categories as records with active status

Equipment categories move from a plain CSV menu (app_configuration.
equipment_categories) into their own table with a real is_active flag —
managed under Configuration > Equipment Categories (list/create/edit/toggle),
same convention as Package.is_active. Equipment.category switches from free
text to a proper FK (equipment_categories.id).

Data migration: every name currently in the CSV menu, plus any distinct
Equipment.category text not already in that CSV (defensive — so no existing
equipment loses its category), becomes one active EquipmentCategory row.
Existing equipment rows are then repointed at the matching new row by name
(case-insensitive).

Revision ID: e3e59dc53636
Revises: 2f5648d844c2
Create Date: 2026-08-03 20:53:41.053221

"""
from datetime import datetime

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e3e59dc53636'
down_revision = '2f5648d844c2'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'equipment_categories',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_by_id', sa.Integer(), nullable=True),
        sa.Column('updated_by_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['created_by_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['updated_by_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name'),
    )

    bind = op.get_bind()
    now = datetime.utcnow()

    csv_raw = bind.execute(sa.text('SELECT equipment_categories FROM app_configuration LIMIT 1')).scalar()
    names = []
    seen = set()
    for token in (csv_raw or '').split(','):
        token = token.strip()
        if token and token.lower() not in seen:
            seen.add(token.lower())
            names.append(token)

    used = bind.execute(sa.text('SELECT DISTINCT category FROM equipments')).fetchall()
    for (val,) in used:
        val = (val or '').strip()
        if val and val.lower() not in seen:
            seen.add(val.lower())
            names.append(val)

    name_to_id = {}
    for name in names:
        new_id = bind.execute(
            sa.text(
                'INSERT INTO equipment_categories (name, is_active, created_at, updated_at) '
                'VALUES (:name, TRUE, :now, :now) RETURNING id'
            ),
            {'name': name, 'now': now},
        ).scalar()
        name_to_id[name.lower()] = new_id

    op.add_column('equipments', sa.Column('category_id', sa.Integer(), nullable=True))
    rows = bind.execute(sa.text('SELECT id, category FROM equipments')).fetchall()
    for eq_id, cat_text in rows:
        cat_id = name_to_id.get((cat_text or '').strip().lower())
        if cat_id:
            bind.execute(
                sa.text('UPDATE equipments SET category_id = :cid WHERE id = :eid'),
                {'cid': cat_id, 'eid': eq_id},
            )

    with op.batch_alter_table('equipments', schema=None) as batch_op:
        batch_op.alter_column('category_id', existing_type=sa.Integer(), nullable=False)
        batch_op.create_foreign_key(
            'fk_equipments_category_id', 'equipment_categories', ['category_id'], ['id']
        )
        batch_op.drop_column('category')

    with op.batch_alter_table('app_configuration', schema=None) as batch_op:
        batch_op.drop_column('equipment_categories')


def downgrade():
    op.add_column(
        'app_configuration', sa.Column('equipment_categories', sa.VARCHAR(length=500), nullable=True)
    )
    op.add_column(
        'equipments', sa.Column('category', sa.VARCHAR(length=100), autoincrement=False, nullable=True)
    )

    bind = op.get_bind()
    rows = bind.execute(sa.text(
        'SELECT e.id, c.name FROM equipments e JOIN equipment_categories c ON e.category_id = c.id'
    )).fetchall()
    for eq_id, name in rows:
        bind.execute(sa.text('UPDATE equipments SET category = :name WHERE id = :eid'), {'name': name, 'eid': eq_id})

    names = bind.execute(sa.text('SELECT name FROM equipment_categories ORDER BY id')).fetchall()
    csv_val = ','.join(n for (n,) in names)
    bind.execute(sa.text('UPDATE app_configuration SET equipment_categories = :v'), {'v': csv_val})

    with op.batch_alter_table('equipments', schema=None) as batch_op:
        batch_op.alter_column('category', existing_type=sa.VARCHAR(length=100), nullable=False)
        batch_op.drop_constraint('fk_equipments_category_id', type_='foreignkey')
        batch_op.drop_column('category_id')

    op.drop_table('equipment_categories')
