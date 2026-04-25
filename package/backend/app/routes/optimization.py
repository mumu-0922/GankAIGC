from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Request
from sqlalchemy.orm import Session, defer, joinedload
from sqlalchemy import func, and_, case
from typing import List, Optional
import json
from app.database import get_db
from app.models.models import User, OptimizationSession, OptimizationSegment, ChangeLog, PaperProject
from app.schemas import (
    OptimizationCreate, SessionResponse, SessionDetailResponse,
    QueueStatusResponse, ProgressUpdate, ChangeLogResponse, ExportConfirmation
)
from app.services.optimization_service import OptimizationService
from app.services.concurrency import concurrency_manager
from app.services.credit_service import CreditService
from app.services.provider_config_service import ProviderConfigService
from app.services.stream_manager import stream_manager
from app.utils.auth import generate_session_id, get_current_user_with_legacy_fallback
from datetime import datetime
import asyncio
from app.config import settings
from sse_starlette.sse import EventSourceResponse

router = APIRouter(prefix="/optimization", tags=["optimization"])


async def run_optimization(session_id: int, db: Session, runtime_provider_config: Optional[dict] = None):
    """后台运行优化任务"""
    session_obj = db.query(OptimizationSession).filter(
        OptimizationSession.id == session_id
    ).first()
    
    if not session_obj:
        return
    
    service = OptimizationService(db, session_obj, runtime_provider_config=runtime_provider_config)
    await service.start_optimization()


@router.post("/start", response_model=SessionResponse)
async def start_optimization(
    data: OptimizationCreate,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user_with_legacy_fallback),
    db: Session = Depends(get_db)
):
    """开始优化任务"""
    if user.card_key:
        usage_limit = user.usage_limit if user.usage_limit is not None else settings.DEFAULT_USAGE_LIMIT
        usage_count = user.usage_count or 0
        # 0 表示无限制
        if usage_limit > 0 and usage_count >= usage_limit:
            raise HTTPException(status_code=403, detail="该卡密已达到使用次数限制")
    else:
        usage_count = user.usage_count or 0
    
    # 验证处理模式
    valid_modes = ['paper_polish', 'paper_enhance', 'paper_polish_enhance', 'emotion_polish']
    if data.processing_mode not in valid_modes:
        raise HTTPException(
            status_code=400,
            detail=f"无效的处理模式。支持的模式: {', '.join(valid_modes)}"
        )

    project = None
    if data.project_id is not None:
        project = (
            db.query(PaperProject)
            .filter(
                PaperProject.id == data.project_id,
                PaperProject.user_id == user.id,
                PaperProject.is_archived.is_(False),
            )
            .first()
        )
        if not project:
            raise HTTPException(status_code=404, detail="论文项目不存在")

    # 根据处理模式设置初始阶段
    if data.processing_mode == 'emotion_polish':
        initial_stage = 'emotion_polish'
    elif data.processing_mode == 'paper_enhance':
        initial_stage = 'enhance'
    else:
        initial_stage = 'polish'
    
    provider_config = None
    if data.billing_mode == "byok":
        if data.polish_config:
            provider_config = {
                "base_url": data.polish_config.base_url,
                "api_key": data.polish_config.api_key,
                "polish_model": data.polish_config.model,
                "enhance_model": data.enhance_config.model if data.enhance_config else data.polish_config.model,
                "emotion_model": data.emotion_config.model if data.emotion_config else None,
            }
        else:
            provider_config = ProviderConfigService(db).get_runtime_config(user)

    polish_model = data.polish_config.model if data.polish_config else None
    polish_api_key = data.polish_config.api_key if data.polish_config else None
    polish_base_url = data.polish_config.base_url if data.polish_config else None
    enhance_model = data.enhance_config.model if data.enhance_config else None
    enhance_api_key = data.enhance_config.api_key if data.enhance_config else None
    enhance_base_url = data.enhance_config.base_url if data.enhance_config else None
    emotion_model = data.emotion_config.model if data.emotion_config else None
    emotion_api_key = data.emotion_config.api_key if data.emotion_config else None
    emotion_base_url = data.emotion_config.base_url if data.emotion_config else None

    if provider_config:
        polish_model = provider_config["polish_model"]
        polish_base_url = provider_config["base_url"]
        enhance_model = provider_config["enhance_model"]
        enhance_base_url = provider_config["base_url"]
        emotion_model = provider_config["emotion_model"]
        emotion_base_url = provider_config["base_url"] if provider_config["emotion_model"] else None
        if not data.polish_config:
            polish_api_key = None
            enhance_api_key = None
            emotion_api_key = None

    # 创建会话
    session_id = generate_session_id()
    session = OptimizationSession(
        user_id=user.id,
        session_id=session_id,
        original_text=data.original_text,
        processing_mode=data.processing_mode,
        billing_mode=data.billing_mode,
        credential_source=(
            "user_saved" if data.billing_mode == "byok" and not data.polish_config else "request"
            if data.billing_mode == "byok"
            else "system"
        ),
        charge_status="not_charged",
        charged_credits=0,
        current_stage=initial_stage,
        status="queued",
        progress=0.0,
        polish_model=polish_model,
        polish_api_key=polish_api_key,
        polish_base_url=polish_base_url,
        enhance_model=enhance_model,
        enhance_api_key=enhance_api_key,
        enhance_base_url=enhance_base_url,
        emotion_model=emotion_model,
        emotion_api_key=emotion_api_key,
        emotion_base_url=emotion_base_url,
        project_id=project.id if project else None,
        task_title=data.task_title.strip() if data.task_title else None,
    )
    
    db.add(session)
    db.flush()
    if data.billing_mode == "platform":
        CreditService(db).hold_platform_credit(user, reason="optimization_start", session_id=session.id)
        session.charge_status = "held"
        session.charged_credits = 0 if user.is_unlimited else 1
    elif data.billing_mode == "byok":
        session.charge_status = "not_charged"
        session.charged_credits = 0

    user.usage_count = usage_count + 1
    db.commit()
    db.refresh(session)
    if project:
        session.project = project
    
    # 添加后台任务
    background_tasks.add_task(run_optimization, session.id, db, provider_config)
    
    return session


@router.get("/status", response_model=QueueStatusResponse)
async def get_queue_status(
    session_id: str = None,
    user: User = Depends(get_current_user_with_legacy_fallback),
    db: Session = Depends(get_db)
):
    """获取队列状态"""
    status = await concurrency_manager.get_status(session_id)
    return QueueStatusResponse(**status)


@router.get("/sessions", response_model=List[SessionResponse])
async def list_sessions(
    limit: int = 20,
    offset: int = 0,
    project_id: Optional[int] = None,
    user: User = Depends(get_current_user_with_legacy_fallback),
    db: Session = Depends(get_db)
):
    """列出用户的所有会话（支持分页）"""
    # 限制最大返回数量为100，避免一次性加载过多数据
    limit = min(limit, 100)
    
    # 查询会话及其原始文本长度和预览文本
    query = db.query(
        OptimizationSession,
        func.length(OptimizationSession.original_text).label('original_char_count'),
        func.substring(OptimizationSession.original_text, 1, 50).label('preview_text')
    ).options(
        joinedload(OptimizationSession.project),
        defer(OptimizationSession.original_text),
        defer(OptimizationSession.error_message)
    ).filter(
        OptimizationSession.user_id == user.id
    )

    if project_id is not None:
        if project_id == 0:
            query = query.filter(OptimizationSession.project_id.is_(None))
        else:
            query = query.filter(OptimizationSession.project_id == project_id)

    results = query.order_by(OptimizationSession.created_at.desc()).limit(limit).offset(offset).all()

    # 构造响应，手动注入 original_char_count 和 preview_text
    sessions = []
    for session, char_count, preview_text in results:
        session.original_char_count = char_count or 0
        session.preview_text = preview_text or ""
        sessions.append(session)
        
    return sessions


@router.get("/sessions/{session_id}", response_model=SessionDetailResponse)
async def get_session_detail(
    session_id: str,
    user: User = Depends(get_current_user_with_legacy_fallback),
    db: Session = Depends(get_db)
):
    """获取会话详情"""
    session = db.query(OptimizationSession).options(joinedload(OptimizationSession.project)).filter(
        OptimizationSession.session_id == session_id,
        OptimizationSession.user_id == user.id
    ).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    
    # 获取段落
    segments = db.query(OptimizationSegment).filter(
        OptimizationSegment.session_id == session.id
    ).order_by(OptimizationSegment.segment_index).all()
    
    return SessionDetailResponse(
        **session.__dict__,
        project_title=session.project_title,
        segments=[seg.__dict__ for seg in segments]
    )


@router.get("/sessions/{session_id}/progress", response_model=ProgressUpdate)
async def get_session_progress(
    session_id: str,
    user: User = Depends(get_current_user_with_legacy_fallback),
    db: Session = Depends(get_db)
):
    """获取会话进度"""
    # 查询完整会话对象，但避免急切加载关联对象
    session = db.query(OptimizationSession).filter(
        OptimizationSession.session_id == session_id,
        OptimizationSession.user_id == user.id
    ).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    
    return ProgressUpdate(
        session_id=session.session_id,
        status=session.status,
        progress=session.progress,
        current_position=session.current_position,
        total_segments=session.total_segments,
        current_stage=session.current_stage,
        error_message=session.error_message
    )


@router.get("/sessions/{session_id}/stream")
async def stream_session_progress(
    session_id: str,
    request: Request,
    user: User = Depends(get_current_user_with_legacy_fallback),
    db: Session = Depends(get_db)
):
    """流式获取会话进度和内容"""
    # 验证用户权限
    session = db.query(OptimizationSession).filter(
        OptimizationSession.session_id == session_id,
        OptimizationSession.user_id == user.id
    ).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    async def event_generator():
        queue = await stream_manager.connect(session_id)
        try:
            while True:
                if await request.is_disconnected():
                    break
                
                # 从队列获取消息，设置超时以便检查连接状态
                try:
                    message = await asyncio.wait_for(queue.get(), timeout=1.0)
                    yield message
                except asyncio.TimeoutError:
                    # 发送心跳注释以保持连接活跃
                    yield ": keep-alive\n\n"
                    
        finally:
            await stream_manager.disconnect(session_id, queue)

    return EventSourceResponse(event_generator())


@router.get("/sessions/{session_id}/changes", response_model=List[ChangeLogResponse])
async def get_session_changes(
    session_id: str,
    user: User = Depends(get_current_user_with_legacy_fallback),
    db: Session = Depends(get_db)
):
    """获取会话的变更对照"""
    session = db.query(OptimizationSession).filter(
        OptimizationSession.session_id == session_id,
        OptimizationSession.user_id == user.id
    ).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    
    latest_log_subquery = db.query(
        ChangeLog.segment_index,
        ChangeLog.stage,
        func.max(ChangeLog.id).label("latest_id")
    ).filter(
        ChangeLog.session_id == session.id
    ).group_by(
        ChangeLog.segment_index,
        ChangeLog.stage
    ).subquery()

    change_logs = db.query(ChangeLog).join(
        latest_log_subquery,
        and_(
            ChangeLog.segment_index == latest_log_subquery.c.segment_index,
            ChangeLog.stage == latest_log_subquery.c.stage,
            ChangeLog.id == latest_log_subquery.c.latest_id
        )
    ).filter(
        ChangeLog.session_id == session.id
    ).order_by(
        ChangeLog.segment_index,
        case((ChangeLog.stage == "polish", 0), else_=1)
    ).all()

    parsed_changes = []
    for change in change_logs:
        detail = None
        if change.changes_detail:
            try:
                detail = json.loads(change.changes_detail)
            except json.JSONDecodeError:
                detail = {"raw": change.changes_detail}

        parsed_changes.append(
            ChangeLogResponse(
                id=change.id,
                segment_index=change.segment_index,
                stage=change.stage,
                before_text=change.before_text,
                after_text=change.after_text,
                changes_detail=detail,
                created_at=change.created_at
            )
        )

    return parsed_changes


@router.post("/sessions/{session_id}/export")
async def export_session(
    session_id: str,
    confirmation: ExportConfirmation,
    user: User = Depends(get_current_user_with_legacy_fallback),
    db: Session = Depends(get_db)
):
    """导出优化结果"""
    if not confirmation.acknowledge_academic_integrity:
        raise HTTPException(
            status_code=400,
            detail="必须确认学术诚信承诺"
        )
    
    session = db.query(OptimizationSession).filter(
        OptimizationSession.session_id == session_id,
        OptimizationSession.user_id == user.id
    ).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    
    if session.status != "completed":
        raise HTTPException(status_code=400, detail="会话未完成")
    
    # 获取所有段落
    segments = db.query(OptimizationSegment).filter(
        OptimizationSegment.session_id == session.id
    ).order_by(OptimizationSegment.segment_index).all()
    
    # 组合最终文本
    final_text = "\n\n".join([
        seg.enhanced_text or seg.polished_text or seg.original_text
        for seg in segments
    ])
    
    # 根据格式返回
    if confirmation.export_format == "txt":
        return {
            "format": "txt",
            "content": final_text,
            "filename": f"optimized_{session_id}.txt"
        }
    else:
        # TODO: 实现 docx 和 pdf 导出
        raise HTTPException(status_code=501, detail="暂不支持此格式")


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
    user: User = Depends(get_current_user_with_legacy_fallback),
    db: Session = Depends(get_db)
):
    """删除会话"""
    session = db.query(OptimizationSession).filter(
        OptimizationSession.session_id == session_id,
        OptimizationSession.user_id == user.id
    ).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    
    db.delete(session)
    db.commit()
    
    return {"message": "会话已删除"}


@router.post("/sessions/{session_id}/retry")
async def retry_session(
    session_id: str,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user_with_legacy_fallback),
    db: Session = Depends(get_db)
):
    """重新尝试处理失败的会话，继续未完成的段落"""
    session = db.query(OptimizationSession).filter(
        OptimizationSession.session_id == session_id,
        OptimizationSession.user_id == user.id
    ).first()

    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    if session.status not in ["failed", "stopped"]:
        raise HTTPException(status_code=400, detail="仅可对失败或已停止的会话执行重试")

    # 保留历史错误信息
    old_error = session.error_message or "未知错误"
    session.status = "queued"
    session.error_message = f"[重试中] 上次失败原因: {old_error}"
    db.commit()

    background_tasks.add_task(run_optimization, session.id, db)

    return {"message": "已重新排队处理未完成段落"}


@router.post("/sessions/{session_id}/stop")
async def stop_session(
    session_id: str,
    user: User = Depends(get_current_user_with_legacy_fallback),
    db: Session = Depends(get_db)
):
    """停止正在进行中的会话"""
    session = db.query(OptimizationSession).filter(
        OptimizationSession.session_id == session_id,
        OptimizationSession.user_id == user.id
    ).first()

    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    if session.status not in ["queued", "processing"]:
        raise HTTPException(status_code=400, detail="只能停止排队中或处理中的会话")

    # 更新状态为 stopped
    session.status = "stopped"
    session.error_message = "用户手动停止"
    db.commit()

    return {"message": "会话已停止"}
