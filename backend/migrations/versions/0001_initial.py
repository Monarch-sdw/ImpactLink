"""Initial ImpactLink schema. See schema snapshot for the frozen initial metadata."""
from alembic import op
from migrations.schema_v1 import Base
revision = '0001'
down_revision = None
branch_labels = None
depends_on = None

def upgrade(): Base.metadata.create_all(bind=op.get_bind())
def downgrade(): Base.metadata.drop_all(bind=op.get_bind())
