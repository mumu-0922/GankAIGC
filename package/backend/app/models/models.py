from sqlalchemy import BigInteger, Boolean, Column, DateTime, Float, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.orm import relationship
from app.database import Base
from app.config import settings
from app.models.browser_agent_constants import (
    BROWSER_AGENT_STATUS_OFFLINE,
    ZHUQUE_AGENT_JOB_STATUS_PENDING,
)
from app.utils.time import utcnow


class User(Base):
    """用户表"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), unique=True, index=True, nullable=True)
    nickname = Column(String(100), nullable=True)
    avatar_url = Column(String(512), nullable=True)
    password_hash = Column(String(255), nullable=True)
    access_link = Column(String(255), unique=True, index=True, nullable=False)
    is_active = Column(Boolean, default=True)
    is_unlimited = Column(Boolean, default=False)
    credit_balance = Column(Integer, default=0)
    created_at = Column(DateTime, default=utcnow)
    last_used = Column(DateTime, nullable=True)
    last_login_at = Column(DateTime, nullable=True)
    usage_limit = Column(Integer, default=settings.DEFAULT_USAGE_LIMIT)
    usage_count = Column(Integer, default=0)
    token_version = Column(Integer, default=0)

    # 朱雀检测配额
    zhuque_free_uses_remaining = Column(Integer, default=20)
    zhuque_total_uses = Column(Integer, default=0)
    
    # 关系
    sessions = relationship("OptimizationSession", back_populates="user")
    prompts = relationship("CustomPrompt", back_populates="user")
    saved_specs = relationship("SavedSpec", back_populates="user", cascade="all, delete-orphan")
    created_invites = relationship("RegistrationInvite", back_populates="created_by_user", foreign_keys="RegistrationInvite.created_by_user_id")
    used_invites = relationship("RegistrationInvite", back_populates="used_by_user", foreign_keys="RegistrationInvite.used_by_user_id")
    redeemed_credit_codes = relationship("CreditCode", back_populates="redeemed_by_user", foreign_keys="CreditCode.redeemed_by_user_id")
    credit_transactions = relationship("CreditTransaction", back_populates="user", cascade="all, delete-orphan")
    provider_config = relationship("UserProviderConfig", back_populates="user", uselist=False, cascade="all, delete-orphan")
    paper_projects = relationship("PaperProject", back_populates="user", cascade="all, delete-orphan")
    browser_agent_pairings = relationship("BrowserAgentPairing", back_populates="user", cascade="all, delete-orphan")
    browser_agents = relationship("BrowserAgent", back_populates="user", cascade="all, delete-orphan")
    zhuque_agent_jobs = relationship("ZhuqueAgentJob", back_populates="user", cascade="all, delete-orphan")


class BrowserAgentPairing(Base):
    """Short-lived pairing code for connecting a user's local browser agent."""
    __tablename__ = "browser_agent_pairings"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    pairing_code_hash = Column(String(128), unique=True, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False, index=True)
    claimed_at = Column(DateTime, nullable=True)
    claimed_by_agent_id = Column(String(128), nullable=True)
    created_at = Column(DateTime, default=utcnow, index=True)

    user = relationship("User", back_populates="browser_agent_pairings")


class BrowserAgent(Base):
    """Paired Chrome extension identity for local-browser Zhuque detection."""
    __tablename__ = "browser_agents"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    agent_id = Column(String(128), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=True)
    token_hash = Column(String(255), nullable=False)
    status = Column(String(32), nullable=False, default=BROWSER_AGENT_STATUS_OFFLINE, index=True)
    last_seen_at = Column(DateTime, nullable=True, index=True)
    created_at = Column(DateTime, default=utcnow, index=True)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)
    revoked_at = Column(DateTime, nullable=True, index=True)
    capabilities_json = Column(Text, nullable=True)
    user_agent = Column(String(512), nullable=True)
    extension_version = Column(String(64), nullable=True)

    user = relationship("User", back_populates="browser_agents")
    zhuque_jobs = relationship("ZhuqueAgentJob", back_populates="claimed_agent", foreign_keys="ZhuqueAgentJob.claimed_by_agent_id")


class ZhuqueAgentJob(Base):
    """Durable Zhuque detection job claimed by a user's local browser agent."""
    __tablename__ = "zhuque_agent_jobs"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(String(128), unique=True, nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    session_id = Column(Integer, ForeignKey("optimization_sessions.id"), nullable=True, index=True)
    segment_id = Column(Integer, ForeignKey("optimization_segments.id"), nullable=True, index=True)
    status = Column(String(32), nullable=False, default=ZHUQUE_AGENT_JOB_STATUS_PENDING, index=True)
    payload_text = Column(Text, nullable=False)
    payload_hash = Column(String(64), nullable=False, index=True)
    result_json = Column(Text, nullable=True)
    progress_json = Column(Text, nullable=True)
    error_code = Column(String(64), nullable=True, index=True)
    error_message = Column(Text, nullable=True)
    claimed_by_agent_id = Column(String(128), ForeignKey("browser_agents.agent_id"), nullable=True, index=True)
    created_at = Column(DateTime, default=utcnow, index=True)
    claimed_at = Column(DateTime, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=False, index=True)
    heartbeat_at = Column(DateTime, nullable=True, index=True)
    attempt_count = Column(Integer, nullable=False, default=0)

    user = relationship("User", back_populates="zhuque_agent_jobs")
    session = relationship("OptimizationSession", back_populates="zhuque_agent_jobs")
    segment = relationship("OptimizationSegment", back_populates="zhuque_agent_jobs")
    claimed_agent = relationship("BrowserAgent", back_populates="zhuque_jobs", foreign_keys=[claimed_by_agent_id])


class CustomPrompt(Base):
    """自定义提示词表"""
    __tablename__ = "custom_prompts"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    name = Column(String(255), nullable=False)
    stage = Column(String(50), nullable=False)  # 'polish' 或 'enhance'
    content = Column(Text, nullable=False)
    is_default = Column(Boolean, default=False)
    is_system = Column(Boolean, default=False)  # 系统预设提示词
    is_active = Column(Boolean, default=True)  # 是否启用
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)
    
    # 关系
    user = relationship("User", back_populates="prompts")


class PaperProject(Base):
    """论文项目表"""
    __tablename__ = "paper_projects"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    is_archived = Column(Boolean, default=False, index=True)
    created_at = Column(DateTime, default=utcnow, index=True)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    user = relationship("User", back_populates="paper_projects")
    sessions = relationship("OptimizationSession", back_populates="project")


class OptimizationSession(Base):
    """优化会话表"""
    __tablename__ = "optimization_sessions"
    __table_args__ = (
        Index(
            "uq_optimization_sessions_one_active_per_user",
            "user_id",
            unique=True,
            postgresql_where=text("status IN ('processing', 'waiting_browser_agent')"),
        ),
    )
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    session_id = Column(String(255), unique=True, index=True)
    original_text = Column(Text)
    current_stage = Column(String(50))  # 'polish' 或 'enhance'
    status = Column(String(50), index=True)  # 'queued', 'processing', 'completed', 'failed'
    progress = Column(Float, default=0.0)
    current_position = Column(Integer, default=0)  # 当前处理的段落位置
    total_segments = Column(Integer, default=0)  # 总段落数
    error_message = Column(Text, nullable=True)
    failed_segment_index = Column(Integer, nullable=True)
    queued_at = Column(DateTime, default=utcnow, index=True)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    worker_id = Column(String(100), nullable=True, index=True)
    worker_attempt_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=utcnow, index=True)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)
    completed_at = Column(DateTime, nullable=True)
    
    # 模型配置
    polish_model = Column(String(100), nullable=True)
    polish_api_key = Column(String(255), nullable=True)
    polish_base_url = Column(String(255), nullable=True)
    polish_api_format = Column(String(40), nullable=True, default="openai_chat")
    enhance_model = Column(String(100), nullable=True)
    enhance_api_key = Column(String(255), nullable=True)
    enhance_base_url = Column(String(255), nullable=True)
    enhance_api_format = Column(String(40), nullable=True, default="openai_chat")
    emotion_model = Column(String(100), nullable=True)
    emotion_api_key = Column(String(255), nullable=True)
    emotion_base_url = Column(String(255), nullable=True)
    emotion_api_format = Column(String(40), nullable=True, default="openai_chat")
    
    # 处理模式: 'paper_polish', 'paper_enhance', 'paper_polish_enhance', 'emotion_polish'
    processing_mode = Column(String(50), default='paper_polish_enhance')
    billing_mode = Column(String(20), default="platform")
    credential_source = Column(String(20), default="system")
    charge_status = Column(String(20), default="not_charged")
    charged_credits = Column(Integer, default=0)
    project_id = Column(Integer, ForeignKey("paper_projects.id"), nullable=True, index=True)
    task_title = Column(String(255), nullable=True)
    zhuque_agent_trace = Column(Text, nullable=True)
    document_format = Column(String(32), nullable=True)
    parse_engine = Column(String(64), nullable=True)
    parse_fallback_used = Column(Boolean, nullable=True)
    parse_trace = Column(Text, nullable=True)
    
    # 关系
    user = relationship("User", back_populates="sessions")
    project = relationship("PaperProject", back_populates="sessions")
    segments = relationship("OptimizationSegment", back_populates="session", cascade="all, delete-orphan")
    history = relationship("SessionHistory", back_populates="session", cascade="all, delete-orphan")
    zhuque_agent_jobs = relationship("ZhuqueAgentJob", back_populates="session")
    task_events = relationship("TaskEvent", back_populates="session", cascade="all, delete-orphan")

    @property
    def completed_segments(self) -> int:
        """Return how many segments finished successfully."""
        return sum(1 for segment in self.segments if segment.status == "completed")

    @property
    def project_title(self) -> str | None:
        return self.project.title if self.project else None


class TaskEvent(Base):
    """Durable SSE outbox event for one optimization session."""

    __tablename__ = "task_events"
    __table_args__ = (
        Index("ix_task_events_session_id_id", "session_id", "id"),
        Index("ix_task_events_session_event_key", "session_id", "event_key"),
    )

    id = Column(BigInteger, primary_key=True)
    session_id = Column(Integer, ForeignKey("optimization_sessions.id", ondelete="CASCADE"), nullable=False)
    event_type = Column(String(64), nullable=False)
    event_key = Column(String(160), nullable=True)
    payload_json = Column(Text, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False, index=True)

    session = relationship("OptimizationSession", back_populates="task_events")


class WorkerLease(Base):
    """Independent worker liveness/boot lease, refreshed even while idle."""

    __tablename__ = "worker_leases"

    worker_id = Column(String(128), primary_key=True)
    boot_id = Column(String(64), nullable=False)
    version = Column(String(64), nullable=True)
    state = Column(String(32), nullable=False, default="idle", index=True)
    capacity = Column(Integer, nullable=False, default=1)
    current_session_id = Column(Integer, ForeignKey("optimization_sessions.id", ondelete="SET NULL"), nullable=True, index=True)
    started_at = Column(DateTime, default=utcnow, nullable=False)
    last_seen_at = Column(DateTime, default=utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)


class OptimizationSegment(Base):
    """优化段落表"""
    __tablename__ = "optimization_segments"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("optimization_sessions.id"), index=True)
    segment_index = Column(Integer, index=True)  # 段落序号
    stage = Column(String(50))  # 'polish' 或 'enhance'
    original_text = Column(Text)
    polished_text = Column(Text, nullable=True)
    enhanced_text = Column(Text, nullable=True)
    status = Column(String(50), index=True)  # 'pending', 'processing', 'completed', 'failed'
    is_title = Column(Boolean, default=False)
    created_at = Column(DateTime, default=utcnow)
    completed_at = Column(DateTime, nullable=True)
    
    # 关系

    # 朱雀检测
    zhuque_detect_rate = Column(Float, nullable=True)
    zhuque_detect_result = Column(Text, nullable=True)
    zhuque_detect_count = Column(Integer, default=0)
    zhuque_reduce_attempt = Column(Integer, default=0)
    zhuque_reduced_text = Column(Text, nullable=True)
    semantic_type = Column(String(64), nullable=True)
    semantic_source = Column(String(64), nullable=True)
    semantic_confidence = Column(Float, nullable=True)
    reduce_allowed = Column(Boolean, nullable=True)
    semantic_reason = Column(String(128), nullable=True)
    char_start = Column(Integer, nullable=True)
    char_end = Column(Integer, nullable=True)
    page_number = Column(Integer, nullable=True)
    bbox_json = Column(Text, nullable=True)
    session = relationship("OptimizationSession", back_populates="segments")
    zhuque_agent_jobs = relationship("ZhuqueAgentJob", back_populates="segment")


class SessionHistory(Base):
    """会话历史表 (用于AI上下文)"""
    __tablename__ = "session_history"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("optimization_sessions.id"))
    stage = Column(String(50))  # 'polish' 或 'enhance'
    history_data = Column(Text)  # JSON格式的历史会话
    is_compressed = Column(Boolean, default=False)
    character_count = Column(Integer, default=0)  # 汉字数量
    created_at = Column(DateTime, default=utcnow)
    
    # 关系
    session = relationship("OptimizationSession", back_populates="history")


class ChangeLog(Base):
    """变更对照记录表 (用于学术审计)"""
    __tablename__ = "change_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("optimization_sessions.id"), index=True)
    segment_index = Column(Integer, index=True)
    stage = Column(String(50), index=True)  # 'polish' 或 'enhance'
    before_text = Column(Text)
    after_text = Column(Text)
    changes_detail = Column(Text)  # JSON格式的详细变更
    created_at = Column(DateTime, default=utcnow)


class QueueStatus(Base):
    """队列状态表"""
    __tablename__ = "queue_status"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(255), unique=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    position = Column(Integer)  # 队列位置
    status = Column(String(50))  # 'queued' 或 'processing'
    created_at = Column(DateTime, default=utcnow)
    started_at = Column(DateTime, nullable=True)


class RegistrationInvite(Base):
    __tablename__ = "registration_invites"

    id = Column(Integer, primary_key=True)
    code = Column(String(64), unique=True, index=True, nullable=False)
    is_active = Column(Boolean, default=True)
    expires_at = Column(DateTime, nullable=True)
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    used_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=utcnow)

    created_by_user = relationship("User", back_populates="created_invites", foreign_keys=[created_by_user_id])
    used_by_user = relationship("User", back_populates="used_invites", foreign_keys=[used_by_user_id])


class CreditCode(Base):
    __tablename__ = "credit_codes"

    id = Column(Integer, primary_key=True)
    code = Column(String(64), unique=True, index=True, nullable=False)
    credit_amount = Column(Integer, nullable=False)
    is_active = Column(Boolean, default=True)
    expires_at = Column(DateTime, nullable=True)
    redeemed_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    redeemed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utcnow)

    redeemed_by_user = relationship("User", back_populates="redeemed_credit_codes", foreign_keys=[redeemed_by_user_id])
    credit_transactions = relationship("CreditTransaction", back_populates="related_code")


class CreditTransaction(Base):
    __tablename__ = "credit_transactions"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    delta = Column(Integer, nullable=False)
    balance_after = Column(Integer, nullable=False)
    reason = Column(String(64), nullable=False)
    related_code_id = Column(Integer, ForeignKey("credit_codes.id"), nullable=True)
    related_session_id = Column(Integer, ForeignKey("optimization_sessions.id"), nullable=True)
    created_at = Column(DateTime, default=utcnow, index=True)

    user = relationship("User", back_populates="credit_transactions")
    related_code = relationship("CreditCode", back_populates="credit_transactions")
    related_session = relationship("OptimizationSession")


class AdminAuditLog(Base):
    """管理员操作审计日志"""
    __tablename__ = "admin_audit_logs"

    id = Column(Integer, primary_key=True)
    admin_username = Column(String(100), nullable=False, index=True)
    action = Column(String(64), nullable=False, index=True)
    target_type = Column(String(64), nullable=True, index=True)
    target_id = Column(Integer, nullable=True, index=True)
    detail = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow, index=True)


class Announcement(Base):
    """后台公告"""
    __tablename__ = "announcements"

    id = Column(Integer, primary_key=True)
    title = Column(String(120), nullable=False)
    content = Column(Text, nullable=False)
    category = Column(String(32), nullable=False, default="notice", index=True)
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime, default=utcnow, index=True)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)


class ZhuquePromptMemory(Base):
    """朱雀提示词进化记忆"""
    __tablename__ = "zhuque_prompt_memories"

    id = Column(Integer, primary_key=True, index=True)
    signature_hash = Column(String(64), nullable=False, index=True)
    failure_signature = Column(Text, nullable=False)
    prompt_patch = Column(Text, nullable=False)
    source = Column(String(32), nullable=False, default="fallback", index=True)
    before_rate = Column(Float, nullable=True)
    after_rate = Column(Float, nullable=True)
    rate_delta = Column(Float, nullable=True)
    uses = Column(Integer, default=0)
    successes = Column(Integer, default=0)
    failures = Column(Integer, default=0)
    enabled = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime, default=utcnow, index=True)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)


class UserProviderConfig(Base):
    __tablename__ = "user_provider_configs"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False, index=True)
    base_url = Column(String(255), nullable=False)
    api_format = Column(String(40), nullable=False, default="openai_chat")
    api_key_encrypted = Column(Text, nullable=False)
    api_key_last4 = Column(String(8), nullable=False)
    polish_model = Column(String(100), nullable=False)
    enhance_model = Column(String(100), nullable=False)
    emotion_model = Column(String(100), nullable=True)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    user = relationship("User", back_populates="provider_config")


class SystemSetting(Base):
    """系统设置表"""
    __tablename__ = "system_settings"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(100), unique=True, nullable=False)
    value = Column(String(255), nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)


class SavedSpec(Base):
    """用户保存的排版规范表"""
    __tablename__ = "saved_specs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    description = Column(String(500), nullable=True)
    spec_json = Column(Text, nullable=False)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    # 关系
    user = relationship("User", back_populates="saved_specs")
