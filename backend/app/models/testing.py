# -*- coding: utf-8 -*-
# @File    : testing.py
# @Desc    : 接口定义、Mock、用例、场景和调试历史表
# @Author  : xuetang-api
# @Date    : 2026-11-12
# @Update  : 2026-11-12 初始化阶段 0 全量表结构

"""接口测试资产模型。请求与步骤细节放 JSON，筛选字段拆成独立列。"""

from sqlalchemy import BigInteger, Boolean, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.dialects.mysql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedMixin, TimestampMixin, table_args


class ApiModule(TimestampMixin, Base):
    """接口目录。parent_id 为空表示根目录。"""

    __tablename__ = "api_module"
    __table_args__ = table_args("接口目录")

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    project_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("project.id"), nullable=False, index=True, comment="项目")
    parent_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("api_module.id"), nullable=True, comment="父目录")
    name: Mapped[str] = mapped_column(String(128), nullable=False, comment="目录名称")
    sort: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"), comment="同级排序")


class ApiDefinition(TimestampMixin, Base):
    """接口定义。request_json 含路径参数、Query、Header 和请求体。"""

    __tablename__ = "api_definition"
    __table_args__ = table_args(
        "接口定义",
        Index("ix_api_definition_lookup", "project_id", "method", "path"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    public_id: Mapped[str] = mapped_column(String(32), nullable=False, unique=True, comment="对外 ID，前缀 API_")
    project_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("project.id"), nullable=False, comment="项目")
    module_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("api_module.id"), nullable=True, comment="所属目录")
    name: Mapped[str] = mapped_column(String(128), nullable=False, comment="接口名称")
    method: Mapped[str] = mapped_column(String(16), nullable=False, comment="请求方法")
    path: Mapped[str] = mapped_column(String(512), nullable=False, comment="请求路径，不含环境 Base URL")
    tags: Mapped[str] = mapped_column(String(255), nullable=False, default="", server_default="", comment="标签，逗号分隔")
    description: Mapped[str] = mapped_column(Text, nullable=False, default="", comment="接口描述")
    request_json: Mapped[dict] = mapped_column(JSON, nullable=False, comment="参数、请求头和请求体")
    revision: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default=text("1"), comment="定义变更版本，用例用它检测接口是否已变"
    )


class ApiResponseExample(TimestampMixin, Base):
    """一份接口可以保存多条响应示例，供对照和 Mock 引用。"""

    __tablename__ = "api_response_example"
    __table_args__ = table_args("接口响应示例")

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    api_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("api_definition.id"), nullable=False, index=True, comment="接口")
    name: Mapped[str] = mapped_column(String(128), nullable=False, comment="示例名称")
    status_code: Mapped[int] = mapped_column(Integer, nullable=False, default=200, server_default=text("200"), comment="HTTP 状态码")
    headers_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict, comment="响应头")
    body: Mapped[str] = mapped_column(Text, nullable=False, default="", comment="响应体")
    description: Mapped[str] = mapped_column(String(255), nullable=False, default="", server_default="", comment="说明")


class MockRule(TimestampMixin, Base):
    """Mock 规则。同一路径按 priority 从小到大匹配，命中第一条即返回。"""

    __tablename__ = "mock_rule"
    __table_args__ = table_args("Mock 规则", Index("ix_mock_rule_project_priority", "project_id", "priority"))

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    project_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("project.id"), nullable=False, comment="项目")
    api_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("api_definition.id"), nullable=True, comment="关联接口，可空表示纯路径规则")
    name: Mapped[str] = mapped_column(String(128), nullable=False, comment="规则名称")
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100, server_default=text("100"), comment="优先级，数值越小越先匹配")
    status_code: Mapped[int] = mapped_column(Integer, nullable=False, default=200, server_default=text("200"), comment="响应状态码")
    headers_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict, comment="响应头")
    body: Mapped[str] = mapped_column(Text, nullable=False, default="", comment="响应体，可包含变量")
    delay_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"), comment="响应延迟毫秒")
    match_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict, comment="路径、方法、Query、Header、请求体匹配条件")
    fault_type: Mapped[str | None] = mapped_column(
        String(32), nullable=True, comment="异常模拟：timeout、error_code、disconnect、slow_start、repeat，空为正常响应"
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("1"), comment="是否启用"
    )


class MockLog(CreatedMixin, Base):
    """Mock 调用流水，用于统计次数和耗时。"""

    __tablename__ = "mock_log"
    __table_args__ = table_args("Mock 调用日志")

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    project_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("project.id"), nullable=False, index=True, comment="项目")
    path: Mapped[str] = mapped_column(String(512), nullable=False, comment="请求路径")
    rule_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("mock_rule.id"), nullable=True, comment="命中的规则，未命中为空")
    elapsed_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"), comment="处理耗时毫秒")
    request_digest: Mapped[str] = mapped_column(Text, nullable=False, default="", comment="请求摘要，不记录敏感头")


class ApiCase(TimestampMixin, Base):
    """单接口用例。请求覆盖、断言、提取和前后置都放在 JSON，便于版本快照。"""

    __tablename__ = "api_case"
    __table_args__ = table_args("单接口用例")

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    public_id: Mapped[str] = mapped_column(String(32), nullable=False, unique=True, comment="对外 ID，前缀 CASE_")
    project_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("project.id"), nullable=False, index=True, comment="项目")
    api_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("api_definition.id"), nullable=True, comment="所属接口，空白用例可空")
    name: Mapped[str] = mapped_column(String(128), nullable=False, comment="用例名称")
    priority: Mapped[str] = mapped_column(
        String(8), nullable=False, default="P2", server_default="P2", comment="优先级 P0 到 P3"
    )
    tags: Mapped[str] = mapped_column(String(255), nullable=False, default="", server_default="", comment="标签，逗号分隔")
    owner_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("sys_user.id"), nullable=True, comment="负责人")
    description: Mapped[str] = mapped_column(Text, nullable=False, default="", comment="用例描述")
    request_json: Mapped[dict] = mapped_column(JSON, nullable=False, comment="相对接口定义的请求覆盖")
    processors_json: Mapped[dict] = mapped_column(JSON, nullable=False, comment="断言、提取、前置和后置处理器")
    review_status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="draft",
        server_default="draft",
        comment="评审状态：draft、reviewing、approved、rejected",
    )
    api_changed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("0"), comment="关联接口变更后是否待更新"
    )


class ApiCaseVersion(CreatedMixin, Base):
    """用例保存时的快照。默认业务层只保留最近 30 条。"""

    __tablename__ = "api_case_version"
    __table_args__ = table_args(
        "用例版本快照",
        Index("ix_case_version_case_no", "case_id", "version_no"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    case_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("api_case.id"), nullable=False, comment="用例")
    version_no: Mapped[int] = mapped_column(Integer, nullable=False, comment="版本号，从 1 递增")
    snapshot_json: Mapped[dict] = mapped_column(JSON, nullable=False, comment="整份用例快照")
    remark: Mapped[str] = mapped_column(String(255), nullable=False, default="", server_default="", comment="修改备注")
    tagged: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("0"), comment="是否打了版本标签"
    )
    operator_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("sys_user.id"), nullable=True, comment="修改人")


class ScenarioModule(TimestampMixin, Base):
    """场景目录。"""

    __tablename__ = "scenario_module"
    __table_args__ = table_args("场景目录")

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    project_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("project.id"), nullable=False, index=True, comment="项目")
    parent_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("scenario_module.id"), nullable=True, comment="父目录")
    name: Mapped[str] = mapped_column(String(128), nullable=False, comment="目录名称")
    sort: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"), comment="同级排序")


class Scenario(TimestampMixin, Base):
    """测试场景。步骤在 scenario_step 中按树存放。"""

    __tablename__ = "scenario"
    __table_args__ = table_args("测试场景")

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    public_id: Mapped[str] = mapped_column(String(32), nullable=False, unique=True, comment="对外 ID，前缀 SCENE_")
    project_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("project.id"), nullable=False, index=True, comment="项目")
    module_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("scenario_module.id"), nullable=True, comment="所属目录")
    name: Mapped[str] = mapped_column(String(128), nullable=False, comment="场景名称")
    level: Mapped[str] = mapped_column(String(8), nullable=False, default="P2", server_default="P2", comment="场景等级 P0 到 P3")
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="enabled", server_default="enabled", comment="状态：enabled、disabled"
    )
    env_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("environment.id"), nullable=True, comment="默认环境")
    tags: Mapped[str] = mapped_column(String(255), nullable=False, default="", server_default="", comment="标签，逗号分隔")
    creator_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("sys_user.id"), nullable=True, comment="创建人")
    description: Mapped[str] = mapped_column(Text, nullable=False, default="", comment="场景描述")


class ScenarioStep(Base):
    """
    场景步骤。

    step_type 取值：case_ref、http、script、sql、wait、transaction、if、loop、foreach、parallel、break。
    控制器的子步骤通过 parent_id 挂接。
    """

    __tablename__ = "scenario_step"
    __table_args__ = table_args("场景步骤", Index("ix_scenario_step_order", "scenario_id", "parent_id", "sort"))

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    scenario_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("scenario.id"), nullable=False, comment="场景")
    parent_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("scenario_step.id"), nullable=True, comment="父步骤")
    step_type: Mapped[str] = mapped_column(String(32), nullable=False, comment="步骤类型")
    name: Mapped[str] = mapped_column(String(128), nullable=False, comment="步骤名称")
    config_json: Mapped[dict] = mapped_column(JSON, nullable=False, comment="步骤配置，结构由 step_type 决定")
    sort: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"), comment="同级排序")


class ScenarioDataset(TimestampMixin, Base):
    """数据驱动文件。每一行数据执行一次完整场景。"""

    __tablename__ = "scenario_dataset"
    __table_args__ = table_args("场景数据驱动文件")

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    scenario_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("scenario.id"), nullable=False, index=True, comment="场景")
    file_path: Mapped[str] = mapped_column(String(512), nullable=False, comment="CSV 或 Excel 文件路径")
    headers_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict, comment="首行变量名")
    thread_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default=text("1"), comment="并发线程数，1 表示串行，最大 20"
    )


class DebugHistory(CreatedMixin, Base):
    """在线调试历史，便于回看某次请求。"""

    __tablename__ = "debug_history"
    __table_args__ = table_args("调试历史")

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    project_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("project.id"), nullable=False, index=True, comment="项目")
    user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("sys_user.id"), nullable=True, comment="调试人")
    target_type: Mapped[str] = mapped_column(String(16), nullable=False, comment="对象类型：api、case、scenario")
    target_id: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default=text("0"), comment="对象主键，未保存的草稿为 0")
    env_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("environment.id"), nullable=True, comment="环境")
    request_json: Mapped[dict] = mapped_column(JSON, nullable=False, comment="当时的请求")
    response_json: Mapped[dict] = mapped_column(JSON, nullable=False, comment="当时的响应")
    elapsed_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"), comment="耗时毫秒")
