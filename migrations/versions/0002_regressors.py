"""Add per-stage metrics to the model run registry."""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"


def upgrade():
    for name in ["count_regressor_type", "value_regressor_type"]:
        op.add_column("model_runs", sa.Column(name, sa.String(64), nullable=True))
    for name in ["count_regressor_rmse", "value_regressor_rmse", "combined_rmse"]:
        op.add_column("model_runs", sa.Column(name, sa.Float(), nullable=True))


def downgrade():
    for name in ["combined_rmse", "value_regressor_rmse", "count_regressor_rmse", "value_regressor_type", "count_regressor_type"]:
        op.drop_column("model_runs", name)
