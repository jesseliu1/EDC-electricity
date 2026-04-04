"""initial_schema

Revision ID: 26998facdffe
Revises:
Create Date: 2026-02-09 15:51:03.394074

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "26998facdffe"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "baseline_definitions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("definition_name", sa.String(length=100), nullable=False, comment="基线定义名称"),
        sa.Column("description", sa.Text(), nullable=True, comment="基线定义说明"),
        sa.Column("expected_duration_minutes", sa.Integer(), nullable=False, comment="预期炉次时长"),
        sa.Column("status", sa.String(length=20), nullable=False, comment="定义状态"),
        sa.Column("created_by", sa.String(length=50), nullable=False, comment="创建人"),
        sa.Column("updated_by", sa.String(length=50), nullable=False, comment="更新人"),
        sa.Column("created_at", sa.BigInteger(), nullable=False, comment="创建时间"),
        sa.Column("updated_at", sa.BigInteger(), nullable=False, comment="更新时间"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_baseline_definitions_name",
        "baseline_definitions",
        ["definition_name"],
        unique=False,
    )
    op.create_index(
        "idx_baseline_definitions_status",
        "baseline_definitions",
        ["status"],
        unique=False,
    )

    op.create_table(
        "settings",
        sa.Column("key", sa.String(length=100), nullable=False, comment="配置键名"),
        sa.Column("value", sa.Text(), nullable=False, comment="配置值JSON"),
        sa.Column("description", sa.String(length=255), nullable=True, comment="配置描述"),
        sa.Column("updated_at", sa.BigInteger(), nullable=False, comment="更新时间"),
        sa.PrimaryKeyConstraint("key"),
    )

    op.create_table(
        "baseline_definition_metrics",
        sa.Column("definition_id", sa.String(length=36), nullable=False, comment="所属基线定义ID"),
        sa.Column("item", sa.String(length=3), nullable=False, comment="指标项号"),
        sa.Column("item_kind", sa.String(length=20), nullable=False, comment="item 语义类型"),
        sa.Column("metric_key", sa.String(length=50), nullable=False, comment="指标业务键"),
        sa.Column("metric_name", sa.String(length=100), nullable=False, comment="指标名称"),
        sa.Column("unit", sa.String(length=20), nullable=True, comment="单位"),
        sa.Column("color", sa.String(length=20), nullable=False, comment="图表颜色"),
        sa.Column("sort_order", sa.Integer(), nullable=False, comment="展示顺序"),
        sa.Column("edc_channel_id", sa.String(length=100), nullable=True, comment="当前绑定通道ID"),
        sa.Column("source_channel_name", sa.String(length=100), nullable=True, comment="通道名称快照"),
        sa.Column("source_channel_label", sa.String(length=255), nullable=True, comment="通道显示标签快照"),
        sa.Column("enabled", sa.Boolean(), nullable=False, comment="是否启用"),
        sa.Column("created_at", sa.BigInteger(), nullable=False, comment="创建时间"),
        sa.Column("updated_at", sa.BigInteger(), nullable=False, comment="更新时间"),
        sa.ForeignKeyConstraint(["definition_id"], ["baseline_definitions.id"]),
        sa.PrimaryKeyConstraint("definition_id", "item"),
    )
    op.create_index(
        "idx_definition_metrics_channel",
        "baseline_definition_metrics",
        ["edc_channel_id"],
        unique=False,
    )
    op.create_index(
        "idx_definition_metrics_metric_key",
        "baseline_definition_metrics",
        ["metric_key"],
        unique=False,
    )
    op.create_index(
        "idx_definition_metrics_sort",
        "baseline_definition_metrics",
        ["definition_id", "sort_order"],
        unique=False,
    )

    op.create_table(
        "baselines",
        sa.Column("definition_id", sa.String(length=36), nullable=False, comment="所属基线定义ID"),
        sa.Column("item", sa.String(length=3), nullable=False, comment="基线版本项"),
        sa.Column("item_kind", sa.String(length=20), nullable=False, comment="item 语义类型"),
        sa.Column("name", sa.String(length=100), nullable=False, comment="基线名称"),
        sa.Column("description", sa.Text(), nullable=True, comment="基线描述"),
        sa.Column("status", sa.String(length=20), nullable=True, comment="基线状态"),
        sa.Column("source_heat_id", sa.String(length=100), nullable=False, comment="生成该基线的来源炉次"),
        sa.Column("selected_start_time", sa.BigInteger(), nullable=False, comment="选区开始时间"),
        sa.Column("selected_end_time", sa.BigInteger(), nullable=False, comment="选区结束时间"),
        sa.Column("effective_from", sa.BigInteger(), nullable=False, comment="生效时间"),
        sa.Column("tolerance_percent", sa.Float(), nullable=False, comment="容许误差百分比"),
        sa.Column("created_by", sa.String(length=50), nullable=False, comment="创建人"),
        sa.Column("updated_by", sa.String(length=50), nullable=False, comment="更新人"),
        sa.Column("created_at", sa.BigInteger(), nullable=False, comment="创建时间"),
        sa.Column("updated_at", sa.BigInteger(), nullable=False, comment="更新时间"),
        sa.Column("published_at", sa.BigInteger(), nullable=True, comment="发布时间"),
        sa.ForeignKeyConstraint(["definition_id"], ["baseline_definitions.id"]),
        sa.PrimaryKeyConstraint("definition_id", "item"),
    )
    op.create_index(
        "idx_baselines_definition_published",
        "baselines",
        ["definition_id", "status", "published_at"],
        unique=False,
    )
    op.create_index(
        "idx_baselines_effective_from",
        "baselines",
        ["effective_from"],
        unique=False,
    )
    op.create_index(
        "idx_baselines_source_heat",
        "baselines",
        ["source_heat_id"],
        unique=False,
    )
    op.create_index(
        "idx_baselines_status",
        "baselines",
        ["status"],
        unique=False,
    )

    op.create_table(
        "heats",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("heat_no", sa.String(length=50), nullable=False, comment="炉次编号"),
        sa.Column("description", sa.Text(), nullable=True, comment="炉次备注"),
        sa.Column("furnace_id", sa.String(length=50), nullable=True, comment="炉号/设备ID"),
        sa.Column("start_time", sa.BigInteger(), nullable=False, comment="炉次真实开始时间"),
        sa.Column("end_time", sa.BigInteger(), nullable=False, comment="炉次真实结束时间"),
        sa.Column("context_start_time", sa.BigInteger(), nullable=False, comment="上下文窗口开始时间"),
        sa.Column("context_end_time", sa.BigInteger(), nullable=False, comment="上下文窗口结束时间"),
        sa.Column("sealed_at", sa.BigInteger(), nullable=False, comment="固化入库时间"),
        sa.Column("source_kind", sa.String(length=30), nullable=False, comment="来源类型"),
        sa.Column("baseline_definition_id", sa.String(length=36), nullable=True, comment="绑定的基线定义ID"),
        sa.Column("baseline_item", sa.String(length=3), nullable=True, comment="绑定的基线版本项"),
        sa.Column("baseline_effective_from_snapshot", sa.BigInteger(), nullable=True, comment="绑定时的基线生效时间快照"),
        sa.Column("deviation_status", sa.String(length=20), nullable=False, comment="偏离度状态"),
        sa.Column("deviation_percent", sa.Float(), nullable=True, comment="最大偏离度"),
        sa.Column("avg_deviation_percent", sa.Float(), nullable=True, comment="平均偏离度"),
        sa.Column("deviation_details_json", sa.Text(), nullable=True, comment="偏离详情JSON"),
        sa.Column("time_offset_percent", sa.Float(), nullable=True, comment="时间偏移比例"),
        sa.Column("mismatch_duration_minutes", sa.Float(), nullable=True, comment="连续不一致时长"),
        sa.Column("cut_reason", sa.String(length=100), nullable=True, comment="切割原因"),
        sa.Column("cut_status", sa.String(length=30), nullable=False, comment="切割状态"),
        sa.Column("status", sa.String(length=20), nullable=False, comment="炉次状态"),
        sa.Column("created_by", sa.String(length=50), nullable=True, comment="创建人"),
        sa.Column("updated_by", sa.String(length=50), nullable=True, comment="更新人"),
        sa.Column("created_at", sa.BigInteger(), nullable=False, comment="创建时间"),
        sa.Column("updated_at", sa.BigInteger(), nullable=False, comment="更新时间"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("heat_no", name="uq_heats_heat_no"),
    )
    op.create_index(
        "idx_heats_baseline_binding",
        "heats",
        ["baseline_definition_id", "baseline_item", "start_time"],
        unique=False,
    )
    op.create_index("idx_heats_deviation_status", "heats", ["deviation_status", "start_time"], unique=False)
    op.create_index("idx_heats_end_time", "heats", ["end_time"], unique=False)
    op.create_index("idx_heats_furnace_time", "heats", ["furnace_id", "start_time"], unique=False)
    op.create_index("idx_heats_start_time", "heats", ["start_time"], unique=False)
    op.create_index("idx_heats_status", "heats", ["status", "start_time"], unique=False)

    op.create_table(
        "metric_series",
        sa.Column("owner_key", sa.String(length=80), nullable=False, comment="所属对象键"),
        sa.Column("item", sa.String(length=3), nullable=False, comment="指标项号"),
        sa.Column("owner_type", sa.String(length=20), nullable=False, comment="所属对象类型 baseline/heat"),
        sa.Column("definition_id", sa.String(length=36), nullable=True, comment="所属基线定义ID"),
        sa.Column("item_kind", sa.String(length=20), nullable=False, comment="item 语义类型"),
        sa.Column("metric_key", sa.String(length=50), nullable=False, comment="指标业务键"),
        sa.Column("metric_name", sa.String(length=100), nullable=False, comment="指标名称"),
        sa.Column("unit", sa.String(length=20), nullable=True, comment="单位"),
        sa.Column("color", sa.String(length=20), nullable=False, comment="图表颜色"),
        sa.Column("sort_order", sa.Integer(), nullable=False, comment="展示顺序"),
        sa.Column("source_channel_id", sa.String(length=100), nullable=True, comment="通道ID快照"),
        sa.Column("source_channel_name", sa.String(length=100), nullable=True, comment="通道名称快照"),
        sa.Column("source_channel_label", sa.String(length=255), nullable=True, comment="通道标签快照"),
        sa.Column("series_json", sa.Text(), nullable=False, comment="指标完整窗口数据JSON"),
        sa.Column("stat_json", sa.Text(), nullable=True, comment="统计信息JSON"),
        sa.Column("created_at", sa.BigInteger(), nullable=False, comment="创建时间"),
        sa.Column("updated_at", sa.BigInteger(), nullable=False, comment="更新时间"),
        sa.PrimaryKeyConstraint("owner_key", "item"),
    )
    op.create_index(
        "idx_metric_series_definition",
        "metric_series",
        ["definition_id"],
        unique=False,
    )
    op.create_index(
        "idx_metric_series_metric_key",
        "metric_series",
        ["metric_key"],
        unique=False,
    )
    op.create_index(
        "idx_metric_series_owner_type",
        "metric_series",
        ["owner_type", "owner_key"],
        unique=False,
    )

    op.create_table(
        "tasks",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("task_no", sa.String(length=50), nullable=False, comment="任务编号"),
        sa.Column("heat_id", sa.String(length=36), nullable=False, comment="对应炉次ID"),
        sa.Column("baseline_definition_id_snapshot", sa.String(length=36), nullable=True, comment="任务创建时基线定义快照"),
        sa.Column("baseline_item_snapshot", sa.String(length=3), nullable=True, comment="任务创建时基线版本项快照"),
        sa.Column("deviation_percent", sa.Float(), nullable=False, comment="任务创建时偏离度快照"),
        sa.Column("deviation_snapshot_json", sa.Text(), nullable=False, comment="偏离详情快照JSON"),
        sa.Column("cause_analysis", sa.Text(), nullable=True, comment="原因分析"),
        sa.Column("improvement", sa.Text(), nullable=True, comment="改善措施"),
        sa.Column("prevention", sa.Text(), nullable=True, comment="预防措施"),
        sa.Column("status", sa.String(length=20), nullable=False, comment="任务状态"),
        sa.Column("created_at", sa.BigInteger(), nullable=False, comment="创建时间"),
        sa.Column("updated_at", sa.BigInteger(), nullable=False, comment="更新时间"),
        sa.Column("completed_at", sa.BigInteger(), nullable=True, comment="完成时间"),
        sa.ForeignKeyConstraint(["heat_id"], ["heats.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("task_no", name="uq_tasks_task_no"),
    )
    op.create_index("idx_tasks_heat", "tasks", ["heat_id", "created_at"], unique=False)
    op.create_index("idx_tasks_status", "tasks", ["status", "created_at"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("idx_tasks_status", table_name="tasks")
    op.drop_index("idx_tasks_heat", table_name="tasks")
    op.drop_table("tasks")
    op.drop_index("idx_metric_series_owner_type", table_name="metric_series")
    op.drop_index("idx_metric_series_metric_key", table_name="metric_series")
    op.drop_index("idx_metric_series_definition", table_name="metric_series")
    op.drop_table("metric_series")
    op.drop_index("idx_heats_status", table_name="heats")
    op.drop_index("idx_heats_start_time", table_name="heats")
    op.drop_index("idx_heats_furnace_time", table_name="heats")
    op.drop_index("idx_heats_end_time", table_name="heats")
    op.drop_index("idx_heats_deviation_status", table_name="heats")
    op.drop_index("idx_heats_baseline_binding", table_name="heats")
    op.drop_table("heats")
    op.drop_index("idx_baselines_status", table_name="baselines")
    op.drop_index("idx_baselines_source_heat", table_name="baselines")
    op.drop_index("idx_baselines_effective_from", table_name="baselines")
    op.drop_index("idx_baselines_definition_published", table_name="baselines")
    op.drop_table("baselines")
    op.drop_index("idx_definition_metrics_sort", table_name="baseline_definition_metrics")
    op.drop_index("idx_definition_metrics_metric_key", table_name="baseline_definition_metrics")
    op.drop_index("idx_definition_metrics_channel", table_name="baseline_definition_metrics")
    op.drop_table("baseline_definition_metrics")
    op.drop_table("settings")
    op.drop_index("idx_baseline_definitions_status", table_name="baseline_definitions")
    op.drop_index("idx_baseline_definitions_name", table_name="baseline_definitions")
    op.drop_table("baseline_definitions")
