# -*- coding: utf-8 -*-
# @File    : platform.py
# @Desc    : 执行、报告、流量、计划、协作、通知、治理、节点和扩展预留表
# @Author  : xuetang-api
# @Date    : 2026-11-12
# @Update  : 2026-11-12 初始化阶段 0 全量表结构

"""执行结果与平台治理模型。"""

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, text
from sqlalchemy.dialects.mysql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedMixin, TimestampMixin, table_args


class ExecTask(TimestampMixin, Base):
    """
    执行任务。

    页面、定时、外部 API 和 CLI 最终都落在这张表。
    node_id 与 node_labels 从第一天保留，本地执行固定指向 local 节点。
    """

    __tablename__ = "exec_task"
    __table_args__ = table_args(
        "执行任务",
        Index("ix_exec_task_project_status", "project_id", "status"),
        Index("ix_exec_task_request", "project_id", "request_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    public_id: Mapped[str] = mapped_column(String(40), nullable=False, unique=True, comment="对外 ID，前缀 TASK_")
    project_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("project.id"), nullable=False, comment="项目")
    task_type: Mapped[str] = mapped_column(
        String(16), nullable=False, comment="类型：case、scenario、perf、replay、plan"
    )
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="pending",
        server_default="pending",
        comment="状态：pending、running、success、failed、stopped、error",
    )
    priority: Mapped[str] = mapped_column(
        String(8), nullable=False, default="P2", server_default="P2", comment="队列优先级 P0 到 P3"
    )
    env_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("environment.id"), nullable=True, comment="执行环境")
    target_type: Mapped[str] = mapped_column(String(16), nullable=False, default="", server_default="", comment="目标类型")
    target_id: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default=text("0"), comment="目标主键")
    variables_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict, comment="本次临时变量")
    run_config_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict, comment="运行配置，压测控制状态也放这里")
    node_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("exec_node.id"), nullable=True, comment="执行节点，本地为 local")
    node_labels: Mapped[str] = mapped_column(
        String(255), nullable=False, default="", server_default="", comment="期望的节点标签，逗号分隔"
    )
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="外部调用幂等号")
    callback_url: Mapped[str] = mapped_column(String(512), nullable=False, default="", server_default="", comment="结束回调地址")
    callback_secret_cipher: Mapped[str] = mapped_column(Text, nullable=False, default="", comment="回调密钥密文")
    progress_done: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"), comment="已完成步骤数")
    progress_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"), comment="总步骤数")
    error_message: Mapped[str] = mapped_column(Text, nullable=False, default="", comment="任务级错误，不含敏感变量原文")
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="开始时间")
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="结束时间")
    creator_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("sys_user.id"), nullable=True, comment="触发人")


class ExecLog(CreatedMixin, Base):
    """任务执行日志，按级别和步骤过滤。"""

    __tablename__ = "exec_log"
    __table_args__ = table_args("执行日志", Index("ix_exec_log_task", "task_id", "id"))

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    task_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("exec_task.id"), nullable=False, comment="任务")
    level: Mapped[str] = mapped_column(String(16), nullable=False, default="INFO", server_default="INFO", comment="级别")
    step_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, comment="关联步骤结果")
    content: Mapped[str] = mapped_column(Text, nullable=False, comment="日志正文")


class TestReport(TimestampMixin, Base):
    """功能报告或性能报告的头部。步骤明细在 report_step。"""

    __tablename__ = "test_report"
    __table_args__ = table_args("测试报告")

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    public_id: Mapped[str] = mapped_column(String(40), nullable=False, unique=True, comment="对外 ID，前缀 RPT_")
    project_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("project.id"), nullable=False, index=True, comment="项目")
    task_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("exec_task.id"), nullable=False, unique=True, comment="来源任务")
    pass_rate: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False, default=0, server_default=text("0"), comment="通过率百分比")
    success_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"), comment="成功数")
    fail_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"), comment="失败数")
    error_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"), comment="错误数")
    elapsed_ms: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default=text("0"), comment="总耗时毫秒")
    archived: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("0"), comment="是否已归档，归档后不参与自动清理"
    )
    perf_baseline: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("0"), comment="是否标记为性能基线"
    )
    summary_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict, comment="概览扩展信息")


class ReportStep(Base):
    """报告中的树形步骤结果。"""

    __tablename__ = "report_step"
    __table_args__ = table_args("报告步骤明细")

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    report_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("test_report.id"), nullable=False, index=True, comment="报告")
    parent_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("report_step.id"), nullable=True, comment="父步骤")
    name: Mapped[str] = mapped_column(String(128), nullable=False, comment="步骤名称")
    status: Mapped[str] = mapped_column(String(16), nullable=False, comment="步骤状态")
    elapsed_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"), comment="耗时毫秒")
    request_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict, comment="请求快照，敏感值已掩码")
    response_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict, comment="响应快照")
    assertions_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict, comment="断言明细")
    error_message: Mapped[str] = mapped_column(Text, nullable=False, default="", comment="失败原因")
    sort: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"), comment="同级排序")


class ReportShare(CreatedMixin, Base):
    """报告公开链接。访问密码只存哈希。"""

    __tablename__ = "report_share"
    __table_args__ = table_args("报告分享")

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    report_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("test_report.id"), nullable=False, index=True, comment="报告")
    token: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, comment="分享令牌")
    expire_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="过期时间，空表示不过期")
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True, comment="访问密码哈希，空表示免密")


class PerfSample(Base):
    """压测秒级采样。"""

    __tablename__ = "perf_sample"
    __table_args__ = table_args("压测秒级采样", Index("ix_perf_sample_task_ts", "task_id", "ts"))

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    task_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("exec_task.id"), nullable=False, comment="压测任务")
    ts: Mapped[datetime] = mapped_column(DateTime, nullable=False, comment="采样时间，秒级")
    tps: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0, server_default=text("0"), comment="每秒事务数")
    concurrency: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"), comment="当时并发数")
    avg_ms: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0, server_default=text("0"), comment="平均响应毫秒")
    p90_ms: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0, server_default=text("0"), comment="P90 响应毫秒")
    p95_ms: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0, server_default=text("0"), comment="P95 响应毫秒")
    p99_ms: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0, server_default=text("0"), comment="P99 响应毫秒")
    error_rate: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False, default=0, server_default=text("0"), comment="错误率百分比")


class PerfApiStat(Base):
    """压测按接口汇总。"""

    __tablename__ = "perf_api_stat"
    __table_args__ = table_args("压测接口维度汇总")

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    task_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("exec_task.id"), nullable=False, index=True, comment="压测任务")
    api_key: Mapped[str] = mapped_column(String(255), nullable=False, comment="接口标识，通常为方法加路径")
    tps: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0, server_default=text("0"), comment="该接口 TPS")
    avg_ms: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0, server_default=text("0"), comment="平均耗时毫秒")
    error_rate: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False, default=0, server_default=text("0"), comment="错误率百分比")
    request_count: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default=text("0"), comment="请求数")


class RecordTask(TimestampMixin, Base):
    """流量录制任务。代理进程由执行阶段按任务拉起。"""

    __tablename__ = "record_task"
    __table_args__ = table_args("流量录制任务")

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    project_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("project.id"), nullable=False, index=True, comment="项目")
    name: Mapped[str] = mapped_column(String(128), nullable=False, comment="任务名称")
    duration_sec: Mapped[int] = mapped_column(Integer, nullable=False, default=600, server_default=text("600"), comment="最长录制秒数")
    max_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1000, server_default=text("1000"), comment="最大条数")
    filter_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict, comment="过滤规则")
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="pending", server_default="pending", comment="状态"
    )
    proxy_port: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="代理监听端口")
    creator_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("sys_user.id"), nullable=True, comment="创建人")


class RecordEntry(Base):
    """单条录制流量，可导出为 HAR。"""

    __tablename__ = "record_entry"
    __table_args__ = table_args("录制条目")

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    task_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("record_task.id"), nullable=False, index=True, comment="录制任务")
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, comment="请求时间")
    method: Mapped[str] = mapped_column(String(16), nullable=False, comment="方法")
    url: Mapped[str] = mapped_column(Text, nullable=False, comment="完整 URL")
    request_json: Mapped[dict] = mapped_column(JSON, nullable=False, comment="请求")
    response_json: Mapped[dict] = mapped_column(JSON, nullable=False, comment="响应")


class ReplayTask(TimestampMixin, Base):
    """流量回放任务，实际执行仍写入 exec_task。"""

    __tablename__ = "replay_task"
    __table_args__ = table_args("流量回放任务")

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    project_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("project.id"), nullable=False, index=True, comment="项目")
    record_task_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("record_task.id"), nullable=False, comment="来源录制")
    env_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("environment.id"), nullable=True, comment="目标环境")
    concurrency: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default=text("1"), comment="回放并发")
    loops: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default=text("1"), comment="循环次数")
    stop_on_failure: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("0"), comment="失败是否停止"
    )
    exec_task_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("exec_task.id"), nullable=True, comment="对应执行任务")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending", server_default="pending", comment="状态")


class TestPlan(TimestampMixin, Base):
    """测试计划。cron_expr 非空时由 beat 到点创建轮次。"""

    __tablename__ = "test_plan"
    __table_args__ = table_args("测试计划")

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    public_id: Mapped[str] = mapped_column(String(40), nullable=False, unique=True, comment="对外 ID，前缀 PLAN_")
    project_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("project.id"), nullable=False, index=True, comment="项目")
    name: Mapped[str] = mapped_column(String(128), nullable=False, comment="计划名称")
    plan_type: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="类型：regression、version、inspect、pre_release"
    )
    env_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("environment.id"), nullable=True, comment="默认环境")
    retry_times: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"), comment="失败重试次数")
    notify_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict, comment="通知规则")
    cron_expr: Mapped[str] = mapped_column(String(64), nullable=False, default="", server_default="", comment="Cron 表达式，空表示不调度")
    description: Mapped[str] = mapped_column(Text, nullable=False, default="", comment="描述")
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="enabled", server_default="enabled", comment="状态"
    )


class TestPlanItem(Base):
    """计划包含的用例或场景。"""

    __tablename__ = "test_plan_item"
    __table_args__ = table_args("测试计划条目")

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    plan_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("test_plan.id"), nullable=False, index=True, comment="计划")
    item_type: Mapped[str] = mapped_column(String(16), nullable=False, comment="条目类型：case 或 scenario")
    item_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="用例或场景主键")


class TestRound(TimestampMixin, Base):
    """一次计划执行产生的轮次。"""

    __tablename__ = "test_round"
    __table_args__ = table_args("测试轮次")

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    public_id: Mapped[str] = mapped_column(String(40), nullable=False, unique=True, comment="对外 ID，前缀 ROUND_")
    plan_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("test_plan.id"), nullable=False, index=True, comment="计划")
    project_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("project.id"), nullable=False, comment="项目")
    version_name: Mapped[str] = mapped_column(String(64), nullable=False, default="", server_default="", comment="业务版本号")
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="pending",
        server_default="pending",
        comment="状态：pending、running、finished、cancelled",
    )
    total_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"), comment="用例总数")
    pass_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"), comment="通过数")
    fail_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"), comment="失败数")
    block_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"), comment="阻塞数")
    pass_rate: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False, default=0, server_default=text("0"), comment="通过率百分比")
    elapsed_ms: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default=text("0"), comment="执行时长毫秒")
    executor_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("sys_user.id"), nullable=True, comment="执行人")


class DefectLink(TimestampMixin, Base):
    """轮次中的失败对象与外部缺陷单的关联。"""

    __tablename__ = "defect_link"
    __table_args__ = table_args("缺陷关联")

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    round_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("test_round.id"), nullable=False, index=True, comment="轮次")
    target_type: Mapped[str] = mapped_column(String(16), nullable=False, comment="失败对象类型")
    target_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="失败对象主键")
    external_key: Mapped[str] = mapped_column(String(64), nullable=False, comment="外部缺陷编号")


class ReviewOrder(TimestampMixin, Base):
    """用例或场景评审单。通过后才允许加入测试计划。"""

    __tablename__ = "review_order"
    __table_args__ = table_args("评审单")

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    project_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("project.id"), nullable=False, index=True, comment="项目")
    target_type: Mapped[str] = mapped_column(String(16), nullable=False, comment="评审对象：case 或 scenario")
    target_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="对象主键")
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="draft",
        server_default="draft",
        comment="状态：draft、reviewing、approved、rejected",
    )
    creator_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("sys_user.id"), nullable=True, comment="发起人")
    reviewer_ids: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict, comment="评审人 ID 列表")


class ReviewOpinion(CreatedMixin, Base):
    """评审意见，可以是总评，也可以指向具体条目。"""

    __tablename__ = "review_opinion"
    __table_args__ = table_args("评审意见")

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    order_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("review_order.id"), nullable=False, index=True, comment="评审单")
    user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("sys_user.id"), nullable=True, comment="发表人")
    content: Mapped[str] = mapped_column(Text, nullable=False, comment="意见正文")
    line_ref: Mapped[str] = mapped_column(String(128), nullable=False, default="", server_default="", comment="逐条意见锚点，总评留空")
    mentions_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict, comment="被提及的用户")


class CollaborationComment(TimestampMixin, Base):
    """用例、场景、报告上的评论。"""

    __tablename__ = "comment"
    __table_args__ = table_args("协作评论")

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    project_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("project.id"), nullable=False, index=True, comment="项目")
    target_type: Mapped[str] = mapped_column(String(16), nullable=False, comment="目标类型：case、scenario、report")
    target_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="目标主键")
    parent_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("comment.id"), nullable=True, comment="父评论")
    user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("sys_user.id"), nullable=True, comment="作者")
    content: Mapped[str] = mapped_column(Text, nullable=False, comment="评论正文")
    mentions_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict, comment="被提及的用户")


class NotifyChannel(TimestampMixin, Base):
    """通知渠道配置。未配置时业务只写站内信。"""

    __tablename__ = "notify_channel"
    __table_args__ = table_args("通知渠道")

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    project_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("project.id"), nullable=True, index=True, comment="项目，空为平台级")
    channel_type: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="渠道：mail、dingtalk、wecom、feishu、inbox"
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False, comment="渠道名称")
    config_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict, comment="渠道参数，密钥加密")
    enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("1"), comment="是否启用"
    )


class NotifyMessage(CreatedMixin, Base):
    """站内信和出站发送记录。"""

    __tablename__ = "notify_message"
    __table_args__ = table_args("通知消息")

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("sys_user.id"), nullable=True, index=True, comment="接收人")
    project_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, comment="项目")
    title: Mapped[str] = mapped_column(String(255), nullable=False, comment="标题")
    content: Mapped[str] = mapped_column(Text, nullable=False, comment="正文")
    channel: Mapped[str] = mapped_column(String(32), nullable=False, default="inbox", server_default="inbox", comment="发送渠道")
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="unread", server_default="unread", comment="状态：unread、read、sent、failed"
    )


class WebhookDelivery(CreatedMixin, Base):
    """外部回调投递记录，支持手工重发。"""

    __tablename__ = "webhook_delivery"
    __table_args__ = table_args("Webhook 投递记录")

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    task_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("exec_task.id"), nullable=False, index=True, comment="任务")
    url: Mapped[str] = mapped_column(String(512), nullable=False, comment="回调地址")
    signature: Mapped[str] = mapped_column(String(128), nullable=False, default="", server_default="", comment="HMAC 签名")
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default=text("1"), comment="第几次尝试")
    response_status: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="对方 HTTP 状态")
    response_body: Mapped[str] = mapped_column(Text, nullable=False, default="", comment="对方响应摘要")


class OpenApiKey(TimestampMixin, Base):
    """外部 API Key。secret 只存哈希，明文只在创建响应中出现一次。"""

    __tablename__ = "open_api_key"
    __table_args__ = table_args("外部 API Key")

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    key_id: Mapped[str] = mapped_column(String(32), nullable=False, unique=True, comment="Key 标识")
    secret_hash: Mapped[str] = mapped_column(String(255), nullable=False, comment="Secret 哈希")
    project_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("project.id"), nullable=False, index=True, comment="绑定项目")
    name: Mapped[str] = mapped_column(String(128), nullable=False, comment="名称")
    scopes: Mapped[str] = mapped_column(
        String(255), nullable=False, default="execute,read", server_default="execute,read", comment="权限范围，仅执行和读报告"
    )
    expire_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="过期时间")
    ip_whitelist: Mapped[str] = mapped_column(String(512), nullable=False, default="", server_default="", comment="IP 白名单，逗号分隔，空表示不限制")
    rpm_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=60, server_default=text("60"), comment="每分钟调用上限")
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="最后调用时间")
    enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("1"), comment="是否启用"
    )


class OpenApiAudit(CreatedMixin, Base):
    """外部调用审计。"""

    __tablename__ = "open_api_audit"
    __table_args__ = table_args("外部 API 调用审计")

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    key_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True, comment="Key 标识")
    path: Mapped[str] = mapped_column(String(255), nullable=False, comment="请求路径")
    ip: Mapped[str] = mapped_column(String(64), nullable=False, default="", server_default="", comment="来源 IP")
    request_id: Mapped[str] = mapped_column(String(64), nullable=False, default="", server_default="", comment="幂等号")
    result: Mapped[str] = mapped_column(String(16), nullable=False, comment="结果：ok 或 denied")


class AlertRule(TimestampMixin, Base):
    """平台告警规则。"""

    __tablename__ = "alert_rule"
    __table_args__ = table_args("告警规则")

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    name: Mapped[str] = mapped_column(String(128), nullable=False, comment="规则名称")
    metric: Mapped[str] = mapped_column(String(64), nullable=False, comment="指标名")
    threshold: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, comment="阈值")
    duration_sec: Mapped[int] = mapped_column(Integer, nullable=False, default=60, server_default=text("60"), comment="持续时间秒")
    level: Mapped[str] = mapped_column(String(16), nullable=False, comment="级别：info、warning、critical")
    channel_ids: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict, comment="通知渠道 ID 列表")
    enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("1"), comment="是否启用"
    )


class AlertEvent(Base):
    """告警历史。相同规则 10 分钟内重复触发时 converged 为真。"""

    __tablename__ = "alert_event"
    __table_args__ = table_args("告警事件")

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    rule_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("alert_rule.id"), nullable=False, index=True, comment="规则")
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="open", server_default="open", comment="处理状态：open、ack、closed"
    )
    message: Mapped[str] = mapped_column(Text, nullable=False, comment="告警内容")
    fired_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, comment="触发时间")
    converged: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("0"), comment="是否被收敛窗口抑制发送"
    )


class RetentionPolicy(TimestampMixin, Base):
    """数据保留天数。project_id 为空表示平台默认。"""

    __tablename__ = "retention_policy"
    __table_args__ = table_args("数据保留策略")

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    project_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("project.id"), nullable=True, unique=True, comment="项目，空为平台默认"
    )
    report_days: Mapped[int] = mapped_column(Integer, nullable=False, default=90, server_default=text("90"), comment="报告保留天数")
    log_days: Mapped[int] = mapped_column(Integer, nullable=False, default=30, server_default=text("30"), comment="执行日志保留天数")
    audit_days: Mapped[int] = mapped_column(Integer, nullable=False, default=180, server_default=text("180"), comment="审计日志保留天数")
    record_days: Mapped[int] = mapped_column(Integer, nullable=False, default=30, server_default=text("30"), comment="录制文件保留天数")


class ExecNode(TimestampMixin, Base):
    """
    执行节点。

    阶段 0 种子写入 name=local 的唯一节点。
    后续集群节点复用本表，不改任务表结构。
    """

    __tablename__ = "exec_node"
    __table_args__ = table_args("执行节点")

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    name: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, comment="节点名称，本地固定为 local")
    address: Mapped[str] = mapped_column(String(255), nullable=False, default="", server_default="", comment="节点地址")
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="offline", server_default="offline", comment="状态：online、offline、draining"
    )
    capacity: Mapped[int] = mapped_column(Integer, nullable=False, default=10, server_default=text("10"), comment="可承载的并发任务数")
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="最后心跳时间")
    metrics_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict, comment="最近一次心跳指标")


class ExecNodeLabel(Base):
    """节点标签，供后续按标签路由。"""

    __tablename__ = "exec_node_label"
    __table_args__ = table_args(
        "执行节点标签",
        Index("uq_exec_node_label", "node_id", "label", unique=True),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    node_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("exec_node.id"), nullable=False, comment="节点")
    label: Mapped[str] = mapped_column(String(64), nullable=False, comment="标签")


class DataTemplate(TimestampMixin, Base):
    """测试数据工厂的字段生成模板。"""

    __tablename__ = "data_template"
    __table_args__ = table_args("数据模板")

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    project_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("project.id"), nullable=True, index=True, comment="项目")
    name: Mapped[str] = mapped_column(String(128), nullable=False, comment="模板名称")
    rules_json: Mapped[dict] = mapped_column(JSON, nullable=False, comment="字段生成规则")


class DataPool(TimestampMixin, Base):
    """数据池。取数策略为 sequence、random、exclusive。"""

    __tablename__ = "data_pool"
    __table_args__ = table_args("数据池")

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    project_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("project.id"), nullable=False, index=True, comment="项目")
    name: Mapped[str] = mapped_column(String(128), nullable=False, comment="池名称")
    category: Mapped[str] = mapped_column(String(64), nullable=False, default="custom", server_default="custom", comment="分类，如 user、course、order")
    pick_policy: Mapped[str] = mapped_column(
        String(16), nullable=False, default="sequence", server_default="sequence", comment="取数策略：sequence、random、exclusive"
    )


class DataPoolItem(TimestampMixin, Base):
    """池中的一条数据。"""

    __tablename__ = "data_pool_item"
    __table_args__ = table_args("数据池条目", Index("ix_data_pool_item_state", "pool_id", "state"))

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    pool_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("data_pool.id"), nullable=False, comment="数据池")
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False, comment="数据内容")
    state: Mapped[str] = mapped_column(
        String(16), nullable=False, default="available", server_default="available", comment="状态：available、used、recycled"
    )


class BizTemplate(TimestampMixin, Base):
    """学堂业务场景模板。snapshot_json 保存可复制的场景结构。"""

    __tablename__ = "biz_template"
    __table_args__ = table_args("业务场景模板")

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    project_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("project.id"), nullable=True, index=True, comment="项目，空为平台预置")
    name: Mapped[str] = mapped_column(String(128), nullable=False, comment="模板名称")
    category: Mapped[str] = mapped_column(String(64), nullable=False, comment="分类")
    version_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default=text("1"), comment="模板版本")
    snapshot_json: Mapped[dict] = mapped_column(JSON, nullable=False, comment="模板快照")


class LlmProvider(TimestampMixin, Base):
    """大模型接入配置。未启用时 AI 功能只提示未配置。"""

    __tablename__ = "llm_provider"
    __table_args__ = table_args("大模型接入配置")

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    name: Mapped[str] = mapped_column(String(64), nullable=False, comment="配置名称")
    base_url: Mapped[str] = mapped_column(String(255), nullable=False, comment="OpenAI 兼容接口地址")
    api_key_cipher: Mapped[str] = mapped_column(Text, nullable=False, default="", comment="API Key 密文")
    model: Mapped[str] = mapped_column(String(64), nullable=False, comment="模型名")
    enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("0"), comment="是否启用"
    )


class AiJob(TimestampMixin, Base):
    """一次 AI 生成或归因任务的输入输出。"""

    __tablename__ = "ai_job"
    __table_args__ = table_args("AI 任务记录")

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    project_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("project.id"), nullable=True, index=True, comment="项目")
    job_type: Mapped[str] = mapped_column(String(32), nullable=False, comment="类型：case_gen、scenario_gen、failure_analysis")
    input_json: Mapped[dict] = mapped_column(JSON, nullable=False, comment="输入")
    output_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict, comment="输出")
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="pending", server_default="pending", comment="状态"
    )


class FailureKnowledge(CreatedMixin, Base):
    """失败归因案例库，先按关键字匹配。"""

    __tablename__ = "failure_knowledge"
    __table_args__ = table_args("失败案例库")

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    category: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="分类：bug、case、env、data、network、platform"
    )
    keywords: Mapped[str] = mapped_column(String(512), nullable=False, comment="匹配关键字，逗号分隔")
    suggestion: Mapped[str] = mapped_column(Text, nullable=False, comment="处理建议")


class ApiWatch(TimestampMixin, Base):
    """定时拉取的 Swagger 或 OpenAPI 地址。"""

    __tablename__ = "api_watch"
    __table_args__ = table_args("接口文档监听")

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    project_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("project.id"), nullable=False, index=True, comment="项目")
    source_url: Mapped[str] = mapped_column(String(512), nullable=False, comment="文档地址")
    cron_expr: Mapped[str] = mapped_column(String(64), nullable=False, default="0 2 * * *", server_default="0 2 * * *", comment="拉取周期")
    enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("1"), comment="是否启用"
    )


class ApiChange(CreatedMixin, Base):
    """一次文档对比产生的变更及影响等级。"""

    __tablename__ = "api_change"
    __table_args__ = table_args("接口变更记录")

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    watch_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("api_watch.id"), nullable=False, index=True, comment="监听配置")
    change_type: Mapped[str] = mapped_column(String(32), nullable=False, comment="变更类型：added、removed、modified")
    detail_json: Mapped[dict] = mapped_column(JSON, nullable=False, comment="变更详情和受影响用例")
    impact_level: Mapped[str] = mapped_column(String(16), nullable=False, default="low", server_default="low", comment="影响等级：high、medium、low")


class ProtocolAsset(TimestampMixin, Base):
    """多协议资产：proto、GraphQL schema、Dubbo 注册中心、WebSocket 定义。"""

    __tablename__ = "protocol_asset"
    __table_args__ = table_args("多协议资产")

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    project_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("project.id"), nullable=False, index=True, comment="项目")
    protocol: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="协议：websocket、grpc、dubbo、graphql"
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False, comment="资产名称")
    content: Mapped[str] = mapped_column(Text, nullable=False, default="", comment="文件或 schema 正文")
    meta_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict, comment="注册中心、TLS 等附加配置")


class ScheduledJob(TimestampMixin, Base):
    """平台内登记的 Cron 任务，便于和 Celery Beat 对账。"""

    __tablename__ = "scheduled_job"
    __table_args__ = table_args("调度任务登记")

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    job_type: Mapped[str] = mapped_column(String(32), nullable=False, comment="任务类型：plan、cleanup、api_watch")
    cron_expr: Mapped[str] = mapped_column(String(64), nullable=False, comment="Cron 表达式")
    ref_id: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default=text("0"), comment="关联对象主键")
    enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("1"), comment="是否启用"
    )
