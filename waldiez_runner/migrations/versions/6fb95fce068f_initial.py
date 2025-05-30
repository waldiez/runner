# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.

"""initial

Revision ID: 6fb95fce068f
Revises:
Create Date: 2025-03-18 15:56:15.287292+00:00
"""

# flake8: noqa
# pylint: skip-file
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "6fb95fce068f"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "clients",
        sa.Column("client_id", sa.String(), nullable=False),
        sa.Column("client_secret", sa.String(), nullable=False),
        sa.Column("audience", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_clients_client_id"), "clients", ["client_id"], unique=True
    )
    op.create_table(
        "tasks",
        sa.Column("client_id", sa.String(), nullable=False),
        sa.Column("flow_id", sa.String(), nullable=False),
        sa.Column("filename", sa.String(), nullable=False),
        sa.Column("input_request_id", sa.String(), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "PENDING",
                "RUNNING",
                "COMPLETED",
                "CANCELLED",
                "FAILED",
                "WAITING_FOR_INPUT",
                name="task_status",
            ),
            nullable=False,
        ),
        sa.Column("results", sa.JSON(), nullable=True),
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_tasks_client_id"), "tasks", ["client_id"], unique=False
    )
    op.create_index(
        op.f("ix_tasks_flow_id"), "tasks", ["flow_id"], unique=False
    )
    op.create_index(op.f("ix_tasks_status"), "tasks", ["status"], unique=False)
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f("ix_tasks_status"), table_name="tasks")
    op.drop_index(op.f("ix_tasks_flow_id"), table_name="tasks")
    op.drop_index(op.f("ix_tasks_client_id"), table_name="tasks")
    op.drop_table("tasks")
    op.drop_index(op.f("ix_clients_client_id"), table_name="clients")
    op.drop_table("clients")
    # ### end Alembic commands ###
