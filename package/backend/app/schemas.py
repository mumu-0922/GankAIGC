from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


class UserCreate(BaseModel):
    """创建用户"""
    username: Optional[str] = None
    nickname: Optional[str] = None
    password_hash: Optional[str] = None
    access_link: str


class UserResponse(BaseModel):
    """用户响应"""
    id: int
    username: Optional[str] = None
    nickname: Optional[str] = None
    access_link: str
    is_active: bool
    is_unlimited: bool = False
    credit_balance: int = 0
    created_at: datetime
    last_used: Optional[datetime] = None
    last_login_at: Optional[datetime] = None
    usage_limit: int
    usage_count: int
    
    model_config = ConfigDict(from_attributes=True)


class RegisterRequest(BaseModel):
    invite_code: str
    username: str = Field(..., min_length=3, max_length=32)
    password: str = Field(..., min_length=8, max_length=128)


class LoginRequest(BaseModel):
    username: str
    password: str


class UserProfileResponse(BaseModel):
    id: int
    username: str
    nickname: Optional[str] = None
    is_active: bool
    is_unlimited: bool
    credit_balance: int
    created_at: datetime
    last_login_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class UserProfileUpdateRequest(BaseModel):
    nickname: str = Field(..., min_length=1, max_length=32)


class InviteCreateRequest(BaseModel):
    code: Optional[str] = None
    expires_at: Optional[datetime] = None


class UserInviteResponse(BaseModel):
    id: int
    code: str
    is_active: bool
    expires_at: Optional[datetime] = None
    created_by_user_id: Optional[int] = None
    used_by_user_id: Optional[int] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CreditCodeCreateRequest(BaseModel):
    code: Optional[str] = None
    credit_amount: int = Field(..., ge=1)
    expires_at: Optional[datetime] = None


class RedeemCodeRequest(BaseModel):
    code: str


class CreditBalanceResponse(BaseModel):
    credit_balance: int
    is_unlimited: bool


class CreditTransactionResponse(BaseModel):
    id: int
    delta: int
    balance_after: int
    reason: str
    reason_label: str
    transaction_type: str
    related_code_id: Optional[int] = None
    related_session_id: Optional[int] = None
    related_session_public_id: Optional[str] = None
    related_session_title: Optional[str] = None
    related_session_processing_mode: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CreditCodeResponse(BaseModel):
    id: int
    code: str
    credit_amount: int
    is_active: bool
    expires_at: Optional[datetime] = None
    redeemed_by_user_id: Optional[int] = None
    redeemed_at: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AdminCreditAdjustRequest(BaseModel):
    amount: int = Field(..., ge=1)
    reason: str = "admin_recharge"


class ProviderConfigUpdateRequest(BaseModel):
    base_url: str
    api_key: str
    polish_model: str
    enhance_model: str
    emotion_model: Optional[str] = None


class ProviderConfigResponse(BaseModel):
    base_url: str
    api_key_last4: str
    polish_model: str
    enhance_model: str
    emotion_model: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class PaperProjectCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None


class PaperProjectUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    is_archived: Optional[bool] = None


class PaperProjectResponse(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    is_archived: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ModelConfig(BaseModel):
    """模型配置"""
    model: str
    api_key: Optional[str] = None
    base_url: Optional[str] = None


class OptimizationCreate(BaseModel):
    """创建优化任务"""
    original_text: str
    processing_mode: str = Field(default='paper_polish_enhance',
                                  description='处理模式: paper_polish, paper_enhance, paper_polish_enhance, emotion_polish')
    billing_mode: str = Field(default="platform", pattern="^(platform|byok)$")
    polish_config: Optional[ModelConfig] = None
    enhance_config: Optional[ModelConfig] = None
    emotion_config: Optional[ModelConfig] = None
    project_id: Optional[int] = None
    task_title: Optional[str] = Field(default=None, max_length=255)


class SegmentResponse(BaseModel):
    """段落响应"""
    id: int
    segment_index: int
    stage: str
    original_text: str
    polished_text: Optional[str] = None
    enhanced_text: Optional[str] = None
    status: str
    is_title: bool
    created_at: datetime
    completed_at: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True)


class SessionResponse(BaseModel):
    """会话响应"""
    id: int
    session_id: str
    current_stage: str
    status: str
    progress: float
    current_position: int
    total_segments: int
    original_char_count: int = 0
    preview_text: Optional[str] = None
    error_message: Optional[str] = None
    processing_mode: str = 'paper_polish_enhance'
    billing_mode: str = "platform"
    credential_source: str = "system"
    charge_status: str = "not_charged"
    charged_credits: int = 0
    project_id: Optional[int] = None
    project_title: Optional[str] = None
    task_title: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True)


class SessionDetailResponse(SessionResponse):
    """会话详细响应"""
    segments: List[SegmentResponse] = []


class QueueStatusResponse(BaseModel):
    """队列状态响应"""
    current_users: int
    max_users: int
    queue_length: int
    your_position: Optional[int] = None
    estimated_wait_time: Optional[int] = None  # 秒


class ProgressUpdate(BaseModel):
    """进度更新"""
    session_id: str
    status: str
    progress: float
    current_position: int
    total_segments: int
    current_stage: str
    error_message: Optional[str] = None


class ChangeLogResponse(BaseModel):
    """变更对照响应"""
    id: int
    segment_index: int
    stage: str
    before_text: str
    after_text: str
    changes_detail: Optional[Dict[str, Any]] = None
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class ExportConfirmation(BaseModel):
    """导出确认"""
    session_id: str
    acknowledge_academic_integrity: bool
    export_format: str = Field(..., pattern="^(docx|md)$")


class UserUsageUpdate(BaseModel):
    """更新用户使用限制"""
    usage_limit: int = Field(..., ge=0)  # 0 表示无限制
    reset_usage_count: bool = False


class DatabaseUpdateRequest(BaseModel):
    """数据库记录更新请求"""
    data: Dict[str, Any]


class PromptCreate(BaseModel):
    """创建提示词"""
    name: str
    stage: str = Field(..., pattern="^(polish|enhance)$")
    content: str
    is_default: bool = False


class PromptUpdate(BaseModel):
    """更新提示词"""
    name: Optional[str] = None
    content: Optional[str] = None
    is_default: Optional[bool] = None
    is_active: Optional[bool] = None


class PromptResponse(BaseModel):
    """提示词响应"""
    id: int
    user_id: Optional[int] = None
    name: str
    stage: str
    content: str
    is_default: bool
    is_system: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)
