"""Initial migration — creates all 5 tables.

Uses VARCHAR for enum-like columns (native_enum=False in SQLAlchemy models),
which avoids PostgreSQL enum case-sensitivity issues and simplifies migrations.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0001_initial'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── conversations ──────────────────────────────────────────────────────────
    op.create_table(
        'conversations',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('conversation_id', sa.String(255), nullable=False),
        sa.Column('agent_version', sa.String(50), nullable=True),
        sa.Column('turns', postgresql.JSONB(), nullable=False),
        sa.Column('feedback', postgresql.JSONB(), nullable=True),
        sa.Column('metadata', postgresql.JSONB(), nullable=True),
        sa.Column('status', sa.String(50), nullable=False, server_default='pending'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('evaluated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_conversations_conversation_id', 'conversations', ['conversation_id'], unique=True)
    op.create_index('ix_conversations_agent_version', 'conversations', ['agent_version'])
    op.create_index('ix_conversations_status', 'conversations', ['status'])

    # ── evaluations ────────────────────────────────────────────────────────────
    op.create_table(
        'evaluations',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('evaluation_id', sa.String(255), nullable=False),
        sa.Column('conversation_id', sa.String(255), sa.ForeignKey('conversations.conversation_id'), nullable=False),
        sa.Column('agent_version', sa.String(50), nullable=True),
        sa.Column('overall_score', sa.Float(), nullable=True),
        sa.Column('response_quality', sa.Float(), nullable=True),
        sa.Column('tool_accuracy', sa.Float(), nullable=True),
        sa.Column('coherence', sa.Float(), nullable=True),
        sa.Column('tool_evaluation', postgresql.JSONB(), nullable=True),
        sa.Column('heuristic_flags', postgresql.JSONB(), nullable=True),
        sa.Column('issues_detected', postgresql.JSONB(), nullable=True),
        sa.Column('llm_judge_raw', postgresql.JSONB(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_evaluations_evaluation_id', 'evaluations', ['evaluation_id'], unique=True)
    op.create_index('ix_evaluations_conversation_id', 'evaluations', ['conversation_id'])
    op.create_index('ix_evaluations_agent_version', 'evaluations', ['agent_version'])

    # ── annotations ───────────────────────────────────────────────────────────
    op.create_table(
        'annotations',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('conversation_id', sa.String(255), nullable=False),
        sa.Column('annotator_id', sa.String(100), nullable=False),
        sa.Column('annotation_type', sa.String(100), nullable=False),
        sa.Column('label', sa.String(100), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('extra', postgresql.JSONB(), nullable=True),
        sa.Column('routing_decision', sa.String(50), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_annotations_conversation_id', 'annotations', ['conversation_id'])
    op.create_index('ix_annotations_annotator_id', 'annotations', ['annotator_id'])

    # ── suggestions ───────────────────────────────────────────────────────────
    op.create_table(
        'suggestions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('suggestion_id', sa.String(255), nullable=False),
        sa.Column('suggestion_type', sa.String(50), nullable=False),
        sa.Column('target', sa.String(255), nullable=True),
        sa.Column('suggestion_text', sa.Text(), nullable=False),
        sa.Column('rationale', sa.Text(), nullable=True),
        sa.Column('expected_impact', sa.Text(), nullable=True),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('failure_pattern', postgresql.JSONB(), nullable=True),
        sa.Column('status', sa.String(50), nullable=False, server_default='pending'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_suggestions_suggestion_id', 'suggestions', ['suggestion_id'], unique=True)
    op.create_index('ix_suggestions_suggestion_type', 'suggestions', ['suggestion_type'])
    op.create_index('ix_suggestions_status', 'suggestions', ['status'])

    # ── evaluator_calibration ─────────────────────────────────────────────────
    op.create_table(
        'evaluator_calibration',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('conversation_id', sa.String(255), nullable=False),
        sa.Column('evaluator_name', sa.String(100), nullable=False),
        sa.Column('metric', sa.String(100), nullable=False),
        sa.Column('llm_score', sa.Float(), nullable=True),
        sa.Column('llm_label', sa.String(100), nullable=True),
        sa.Column('human_score', sa.Float(), nullable=True),
        sa.Column('human_label', sa.String(100), nullable=True),
        sa.Column('agreement', sa.Boolean(), nullable=True),
        sa.Column('agreement_delta', sa.Float(), nullable=True),
        sa.Column('extra', postgresql.JSONB(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_calibration_conversation_id', 'evaluator_calibration', ['conversation_id'])
    op.create_index('ix_calibration_evaluator_name', 'evaluator_calibration', ['evaluator_name'])


def downgrade() -> None:
    op.drop_table('evaluator_calibration')
    op.drop_table('suggestions')
    op.drop_table('annotations')
    op.drop_table('evaluations')
    op.drop_table('conversations')
