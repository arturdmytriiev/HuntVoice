"""Initial schema - create reservations, call_sessions, and audit_log tables.

Revision ID: 001
Revises:
Create Date: 2025-12-29

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create initial database tables."""
    # Create reservations table
    op.create_table(
        'reservations',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('phone', sa.String(length=20), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('time', sa.Time(), nullable=False),
        sa.Column('guests', sa.Integer(), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='pending'),
        sa.Column('canceled_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_reservations'))
    )

    # Create indexes for reservations
    op.create_index(op.f('ix_reservations_name'), 'reservations', ['name'], unique=False)
    op.create_index(op.f('ix_reservations_phone'), 'reservations', ['phone'], unique=False)
    op.create_index(op.f('ix_reservations_date'), 'reservations', ['date'], unique=False)
    op.create_index(op.f('ix_reservations_status'), 'reservations', ['status'], unique=False)
    op.create_index(op.f('ix_reservations_created_at'), 'reservations', ['created_at'], unique=False)
    op.create_index('ix_reservations_date_time', 'reservations', ['date', 'time'], unique=False)
    op.create_index('ix_reservations_status_date', 'reservations', ['status', 'date'], unique=False)
    op.create_index('ix_reservations_phone_date', 'reservations', ['phone', 'date'], unique=False)

    # Create call_sessions table
    op.create_table(
        'call_sessions',
        sa.Column('call_id', sa.String(length=100), nullable=False),
        sa.Column('phone_number', sa.String(length=20), nullable=False),
        sa.Column('intent', sa.String(length=50), nullable=False, server_default='unknown'),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='initiated'),
        sa.Column('state_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('current_step', sa.String(length=100), nullable=True),
        sa.Column('error_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('call_id', name=op.f('pk_call_sessions'))
    )

    # Create indexes for call_sessions
    op.create_index(op.f('ix_call_sessions_phone_number'), 'call_sessions', ['phone_number'], unique=False)
    op.create_index(op.f('ix_call_sessions_status'), 'call_sessions', ['status'], unique=False)
    op.create_index('ix_call_sessions_phone_started', 'call_sessions', ['phone_number', 'started_at'], unique=False)
    op.create_index('ix_call_sessions_status_started', 'call_sessions', ['status', 'started_at'], unique=False)

    # Create audit_log table
    op.create_table(
        'audit_log',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('action', sa.String(length=50), nullable=False),
        sa.Column('entity_type', sa.String(length=50), nullable=False),
        sa.Column('entity_id', sa.String(length=100), nullable=False),
        sa.Column('user_id', sa.String(length=100), nullable=True),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_audit_log'))
    )

    # Create indexes for audit_log
    op.create_index(op.f('ix_audit_log_action'), 'audit_log', ['action'], unique=False)
    op.create_index(op.f('ix_audit_log_entity_type'), 'audit_log', ['entity_type'], unique=False)
    op.create_index(op.f('ix_audit_log_entity_id'), 'audit_log', ['entity_id'], unique=False)
    op.create_index(op.f('ix_audit_log_user_id'), 'audit_log', ['user_id'], unique=False)
    op.create_index(op.f('ix_audit_log_created_at'), 'audit_log', ['created_at'], unique=False)
    op.create_index('ix_audit_log_entity', 'audit_log', ['entity_type', 'entity_id'], unique=False)
    op.create_index('ix_audit_log_action_created', 'audit_log', ['action', 'created_at'], unique=False)
    op.create_index('ix_audit_log_user_created', 'audit_log', ['user_id', 'created_at'], unique=False)


def downgrade() -> None:
    """Drop all tables."""
    # Drop audit_log indexes and table
    op.drop_index('ix_audit_log_user_created', table_name='audit_log')
    op.drop_index('ix_audit_log_action_created', table_name='audit_log')
    op.drop_index('ix_audit_log_entity', table_name='audit_log')
    op.drop_index(op.f('ix_audit_log_created_at'), table_name='audit_log')
    op.drop_index(op.f('ix_audit_log_user_id'), table_name='audit_log')
    op.drop_index(op.f('ix_audit_log_entity_id'), table_name='audit_log')
    op.drop_index(op.f('ix_audit_log_entity_type'), table_name='audit_log')
    op.drop_index(op.f('ix_audit_log_action'), table_name='audit_log')
    op.drop_table('audit_log')

    # Drop call_sessions indexes and table
    op.drop_index('ix_call_sessions_status_started', table_name='call_sessions')
    op.drop_index('ix_call_sessions_phone_started', table_name='call_sessions')
    op.drop_index(op.f('ix_call_sessions_status'), table_name='call_sessions')
    op.drop_index(op.f('ix_call_sessions_phone_number'), table_name='call_sessions')
    op.drop_table('call_sessions')

    # Drop reservations indexes and table
    op.drop_index('ix_reservations_phone_date', table_name='reservations')
    op.drop_index('ix_reservations_status_date', table_name='reservations')
    op.drop_index('ix_reservations_date_time', table_name='reservations')
    op.drop_index(op.f('ix_reservations_created_at'), table_name='reservations')
    op.drop_index(op.f('ix_reservations_status'), table_name='reservations')
    op.drop_index(op.f('ix_reservations_date'), table_name='reservations')
    op.drop_index(op.f('ix_reservations_phone'), table_name='reservations')
    op.drop_index(op.f('ix_reservations_name'), table_name='reservations')
    op.drop_table('reservations')
