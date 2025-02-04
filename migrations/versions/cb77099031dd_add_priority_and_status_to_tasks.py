"""Add priority and status to tasks

Revision ID: cb77099031dd
Revises: 
Create Date: 2024-12-30 14:41:05.606754

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'cb77099031dd'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('task', schema=None) as batch_op:
        batch_op.add_column(sa.Column('priority', sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column('status', sa.String(length=50), nullable=False))
        batch_op.drop_constraint('task_board_id_fkey', type_='foreignkey')
        batch_op.create_foreign_key(None, 'board', ['board_id'], ['id'], ondelete='CASCADE')

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('task', schema=None) as batch_op:
        batch_op.drop_constraint(None, type_='foreignkey')
        batch_op.create_foreign_key('task_board_id_fkey', 'board', ['board_id'], ['id'])
        batch_op.drop_column('status')
        batch_op.drop_column('priority')

    # ### end Alembic commands ###
