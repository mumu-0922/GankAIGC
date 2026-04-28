from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, ForeignKey, Float
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base
from app.config import settings


class User(Base):
    """用户表"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), unique=True, index=True, nullable=True)
    nickname = Column(String(100), nullable=True)
    password_hash = Column(String(255), nullable=True)
    access_link = Column(String(255), unique=True, index=True, nullable=False)
    is_active = Column(Boolean, default=True)
    is_unlimited = Column(Boolean, default=False)
    credit_balance = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_used = Column(DateTime, nullable=True)
    last_login_at = Column(DateTime, nullable=True)
    usage_limit = Column(Integer, default=settings.DEFAULT_USAGE_LIMIT)
    usage_count = Column(Integer, default=0)
    
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
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
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
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="paper_projects")
    sessions = relationship("OptimizationSession", back_populates="project")


class OptimizationSession(Base):
    """优化会话表"""
    __tablename__ = "optimization_sessions"
    
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
    queued_at = Column(DateTime, default=datetime.utcnow, index=True)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    worker_id = Column(String(100), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    
    # 模型配置
    polish_model = Column(String(100), nullable=True)
    polish_api_key = Column(String(255), nullable=True)
    polish_base_url = Column(String(255), nullable=True)
    enhance_model = Column(String(100), nullable=True)
    enhance_api_key = Column(String(255), nullable=True)
    enhance_base_url = Column(String(255), nullable=True)
    emotion_model = Column(String(100), nullable=True)
    emotion_api_key = Column(String(255), nullable=True)
    emotion_base_url = Column(String(255), nullable=True)
    
    # 处理模式: 'paper_polish', 'paper_enhance', 'paper_polish_enhance', 'emotion_polish'
    processing_mode = Column(String(50), default='paper_polish_enhance')
    billing_mode = Column(String(20), default="platform")
    credential_source = Column(String(20), default="system")
    charge_status = Column(String(20), default="not_charged")
    charged_credits = Column(Integer, default=0)
    project_id = Column(Integer, ForeignKey("paper_projects.id"), nullable=True, index=True)
    task_title = Column(String(255), nullable=True)
    
    # 关系
    user = relationship("User", back_populates="sessions")
    project = relationship("PaperProject", back_populates="sessions")
    segments = relationship("OptimizationSegment", back_populates="session", cascade="all, delete-orphan")
    history = relationship("SessionHistory", back_populates="session", cascade="all, delete-orphan")

    @property
    def completed_segments(self) -> int:
        """Return how many segments finished successfully."""
        return sum(1 for segment in self.segments if segment.status == "completed")

    @property
    def project_title(self) -> str | None:
        return self.project.title if self.project else None


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
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    
    # 关系
    session = relationship("OptimizationSession", back_populates="segments")


class SessionHistory(Base):
    """会话历史表 (用于AI上下文)"""
    __tablename__ = "session_history"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("optimization_sessions.id"))
    stage = Column(String(50))  # 'polish' 或 'enhance'
    history_data = Column(Text)  # JSON格式的历史会话
    is_compressed = Column(Boolean, default=False)
    character_count = Column(Integer, default=0)  # 汉字数量
    created_at = Column(DateTime, default=datetime.utcnow)
    
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
    created_at = Column(DateTime, default=datetime.utcnow)


class QueueStatus(Base):
    """队列状态表"""
    __tablename__ = "queue_status"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(255), unique=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    position = Column(Integer)  # 队列位置
    status = Column(String(50))  # 'queued' 或 'processing'
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)


class RegistrationInvite(Base):
    __tablename__ = "registration_invites"

    id = Column(Integer, primary_key=True)
    code = Column(String(64), unique=True, index=True, nullable=False)
    is_active = Column(Boolean, default=True)
    expires_at = Column(DateTime, nullable=True)
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    used_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

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
    created_at = Column(DateTime, default=datetime.utcnow)

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
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    user = relationship("User", back_populates="credit_transactions")
    related_code = relationship("CreditCode", back_populates="credit_transactions")
    related_session = relationship("OptimizationSession")


class UserProviderConfig(Base):
    __tablename__ = "user_provider_configs"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False, index=True)
    base_url = Column(String(255), nullable=False)
    api_key_encrypted = Column(Text, nullable=False)
    api_key_last4 = Column(String(8), nullable=False)
    polish_model = Column(String(100), nullable=False)
    enhance_model = Column(String(100), nullable=False)
    emotion_model = Column(String(100), nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="provider_config")


class SystemSetting(Base):
    """系统设置表"""
    __tablename__ = "system_settings"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(100), unique=True, nullable=False)
    value = Column(String(255), nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class SavedSpec(Base):
    """用户保存的排版规范表"""
    __tablename__ = "saved_specs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    description = Column(String(500), nullable=True)
    spec_json = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关系
    user = relationship("User", back_populates="saved_specs")
