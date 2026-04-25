"""
文章预处理服务

功能：
1. 确定性分段：基于空行、标题模式等规则切分段落
2. 分块 AI 标记：每块限制段落数/字符数，防止上下文过大
3. 标记组装：在原文段落前插入 <!-- wf:type=xxx --> 标记
4. 一致性校验：确保标记后文本与原文内容一致
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple


class PreprocessPhase(str, Enum):
    """预处理阶段"""
    SPLITTING = "splitting"
    MARKING = "marking"
    VALIDATING = "validating"
    COMPLETED = "completed"
    ERROR = "error"


@dataclass
class PreprocessConfig:
    """预处理配置"""
    chunk_paragraphs: int = 40
    chunk_chars: int = 8000
    context_overlap: int = 2
    max_retries: int = 2


@dataclass
class ParagraphInfo:
    """段落信息"""
    index: int
    text: str
    paragraph_type: Optional[str] = None
    confidence: float = 0.0
    is_rule_identified: bool = False


@dataclass
class PreprocessProgress:
    """预处理进度"""
    phase: PreprocessPhase
    total_paragraphs: int
    processed_paragraphs: int
    current_chunk: int
    total_chunks: int
    message: str
    error: Optional[str] = None
    is_recoverable: bool = True


@dataclass
class PreprocessResult:
    """预处理结果"""
    success: bool
    marked_text: str = ""
    paragraphs: List[ParagraphInfo] = field(default_factory=list)
    type_statistics: Dict[str, int] = field(default_factory=dict)
    integrity_check_passed: bool = False
    original_hash: str = ""
    warnings: List[str] = field(default_factory=list)
    error: Optional[str] = None


# 有效的段落类型
VALID_PARAGRAPH_TYPES = frozenset({
    "title_cn", "title_en",
    "abstract_cn", "abstract_en",
    "keywords_cn", "keywords_en",
    "heading_1", "heading_2", "heading_3",
    "body",
    "reference", "acknowledgement",
    "figure_caption", "table_caption",
})


# AI 分块标记提示词
AI_CHUNK_MARKING_PROMPT = """你是一个论文结构识别专家。请分析以下段落，判断每个段落的类型。

可选的段落类型：
- title_cn: 中文论文标题
- title_en: 英文论文标题
- abstract_cn: 中文摘要内容
- abstract_en: 英文摘要内容
- keywords_cn: 中文关键词
- keywords_en: 英文关键词
- heading_1: 一级标题（章标题）
- heading_2: 二级标题（节标题）
- heading_3: 三级标题
- body: 正文段落
- reference: 参考文献条目
- acknowledgement: 致谢内容
- figure_caption: 图片标题
- table_caption: 表格标题

请以 JSON 数组格式返回，每个元素包含 "index" 和 "type" 字段。
只返回 JSON，不要其他文字，不要使用 markdown 代码块。

{context_before}

【待标记段落】
{paragraphs}

{context_after}"""


# 规则识别模式
STRUCTURE_PATTERNS = {
    "title_cn": [
        r"^[\u4e00-\u9fa5]{2,50}$",
    ],
    "title_en": [
        r"^[A-Z][a-zA-Z\s\-:]+$",
    ],
    "abstract_cn": [
        r"^摘\s*要[:：]?",
        r"^内容摘要[:：]?",
    ],
    "abstract_en": [
        r"^abstract[:：]?",
        r"^summary[:：]?",
    ],
    "keywords_cn": [
        r"^关键词[:：]?",
        r"^关键字[:：]?",
    ],
    "keywords_en": [
        r"^key\s*words[:：]?",
        r"^keywords[:：]?",
    ],
    "heading_1": [
        r"^第[一二三四五六七八九十]+章",
        r"^[一二三四五六七八九十]+、",
        r"^\d+[\s\.]",
    ],
    "heading_2": [
        r"^[（\(][一二三四五六七八九十]+[）\)]",
        r"^\d+\.\d+[\s\.]?",
    ],
    "heading_3": [
        r"^\d+\.\d+\.\d+[\s\.]?",
    ],
    "reference": [
        r"^参考文献",
        r"^references",
    ],
    "acknowledgement": [
        r"^致\s*谢",
        r"^谢\s*辞",
        r"^acknowledgement",
    ],
}


ProgressCallback = Callable[[PreprocessProgress], None]


class ArticlePreprocessor:
    """文章预处理器"""

    def __init__(self, ai_service: Any, config: Optional[PreprocessConfig] = None):
        self.ai_service = ai_service
        self.config = config or PreprocessConfig()

    async def preprocess(
        self,
        text: str,
        progress_callback: Optional[ProgressCallback] = None
    ) -> PreprocessResult:
        """
        执行完整预处理流程

        Args:
            text: 原始文章文本
            progress_callback: 进度回调函数

        Returns:
            PreprocessResult 预处理结果
        """
        warnings: List[str] = []

        # 计算原文 hash
        original_hash = self._compute_hash(text)

        def notify(phase: PreprocessPhase, processed: int, total: int,
                   chunk: int, chunks: int, msg: str, error: str = None):
            if progress_callback:
                progress_callback(PreprocessProgress(
                    phase=phase,
                    total_paragraphs=total,
                    processed_paragraphs=processed,
                    current_chunk=chunk,
                    total_chunks=chunks,
                    message=msg,
                    error=error,
                ))

        try:
            # 阶段 1：确定性分段
            notify(PreprocessPhase.SPLITTING, 0, 0, 0, 0, "正在分割段落...")
            paragraphs = self.split_paragraphs(text)
            total_paragraphs = len(paragraphs)

            if total_paragraphs == 0:
                return PreprocessResult(
                    success=False,
                    error="文章内容为空或无法分段",
                    original_hash=original_hash,
                )

            notify(PreprocessPhase.SPLITTING, total_paragraphs, total_paragraphs,
                   0, 0, f"分割完成，共 {total_paragraphs} 个段落")

            # 创建段落信息列表
            paragraph_infos: List[ParagraphInfo] = [
                ParagraphInfo(index=i, text=p) for i, p in enumerate(paragraphs)
            ]

            # 阶段 2：分块 AI 标记
            chunks = self.create_chunks(paragraphs)
            total_chunks = len(chunks)

            notify(PreprocessPhase.MARKING, 0, total_paragraphs, 0, total_chunks,
                   f"开始标记，共 {total_chunks} 个分块")

            processed_count = 0
            for chunk_idx, (start, end) in enumerate(chunks):
                notify(PreprocessPhase.MARKING, processed_count, total_paragraphs,
                       chunk_idx + 1, total_chunks,
                       f"正在处理分块 {chunk_idx + 1}/{total_chunks}")

                # 调用 AI 标记分块
                try:
                    chunk_results = await self.mark_chunk(
                        paragraphs, start, end, paragraphs
                    )

                    # 更新段落类型
                    for result in chunk_results:
                        idx = result.get("index")
                        ptype = result.get("type", "body")
                        confidence = result.get("confidence", 0.8)

                        if idx is not None and start <= idx < end:
                            if ptype in VALID_PARAGRAPH_TYPES:
                                paragraph_infos[idx].paragraph_type = ptype
                                paragraph_infos[idx].confidence = confidence
                            else:
                                paragraph_infos[idx].paragraph_type = "body"
                                paragraph_infos[idx].confidence = 0.5

                except Exception as e:
                    # AI 标记失败，回退到规则识别
                    warnings.append(f"分块 {chunk_idx + 1} AI 标记失败: {str(e)}，使用规则识别")
                    for i in range(start, end):
                        ptype = self.identify_paragraph_type(paragraphs[i])
                        paragraph_infos[i].paragraph_type = ptype
                        paragraph_infos[i].is_rule_identified = True

                processed_count = end

            # 填充未标记的段落（使用规则识别）
            for para in paragraph_infos:
                if para.paragraph_type is None:
                    para.paragraph_type = self.identify_paragraph_type(para.text)
                    para.is_rule_identified = True

            # 阶段 3：组装标记文本
            notify(PreprocessPhase.VALIDATING, total_paragraphs, total_paragraphs,
                   total_chunks, total_chunks, "正在组装标记文本...")

            marked_text = self.assemble_marked_text(paragraph_infos)

            # 阶段 4：一致性校验
            integrity_passed, differences = self.verify_integrity(text, marked_text)

            if not integrity_passed:
                warnings.append(f"原文一致性校验失败，发现 {len(differences)} 处差异")

            # 统计类型分布
            type_stats: Dict[str, int] = {}
            for para in paragraph_infos:
                ptype = para.paragraph_type or "body"
                type_stats[ptype] = type_stats.get(ptype, 0) + 1

            notify(PreprocessPhase.COMPLETED, total_paragraphs, total_paragraphs,
                   total_chunks, total_chunks, "预处理完成")

            return PreprocessResult(
                success=True,
                marked_text=marked_text,
                paragraphs=paragraph_infos,
                type_statistics=type_stats,
                integrity_check_passed=integrity_passed,
                original_hash=original_hash,
                warnings=warnings,
            )

        except Exception as e:
            notify(PreprocessPhase.ERROR, 0, 0, 0, 0, f"预处理失败: {str(e)}", str(e))
            return PreprocessResult(
                success=False,
                error=str(e),
                original_hash=original_hash,
                warnings=warnings,
            )

    def split_paragraphs(self, text: str) -> List[str]:
        """
        确定性分段策略

        规则：
        1. 标准化换行符
        2. 特殊标记预处理
        3. 按空行分割
        4. 清理并过滤空段落
        """
        # 标准化换行符
        text = text.replace('\r\n', '\n').replace('\r', '\n')

        # 特殊标记预处理
        special_markers = ['[[PAGEBREAK]]', '[[SECTIONBREAK]]', '---pagebreak---', '---sectionbreak---']
        for marker in special_markers:
            text = text.replace(marker, f'\n\n{marker}\n\n')

        # 按空行分割
        raw_paragraphs = re.split(r'\n\s*\n', text)

        # 清理并过滤空段落
        paragraphs = []
        for p in raw_paragraphs:
            cleaned = p.strip()
            if cleaned:
                paragraphs.append(cleaned)

        return paragraphs

    def create_chunks(self, paragraphs: List[str]) -> List[Tuple[int, int]]:
        """
        创建分块

        策略：
        1. 每块不超过 chunk_paragraphs 段
        2. 每块不超过 chunk_chars 字符
        3. 避免在标题后断开
        """
        if not paragraphs:
            return []

        chunks = []
        start = 0
        current_chars = 0

        for i, para in enumerate(paragraphs):
            para_len = len(para)
            should_split = False

            # 段落数达到上限
            if (i - start) >= self.config.chunk_paragraphs:
                should_split = True

            # 字符数即将超限
            if current_chars + para_len > self.config.chunk_chars and i > start:
                should_split = True

            if should_split:
                # 检查上一段是否为标题
                prev_para = paragraphs[i - 1] if i > 0 else ""
                if self._is_likely_heading(prev_para) and not self._is_likely_heading(para):
                    # 将标题包含在下一块
                    if i - 1 > start:
                        chunks.append((start, i - 1))
                        start = i - 1
                        current_chars = len(prev_para)
                    # 如果只有一个标题，不分割
                else:
                    chunks.append((start, i))
                    start = i
                    current_chars = 0

            current_chars += para_len

        # 添加最后一块
        if start < len(paragraphs):
            chunks.append((start, len(paragraphs)))

        return chunks

    async def mark_chunk(
        self,
        all_paragraphs: List[str],
        chunk_start: int,
        chunk_end: int,
        context_paragraphs: List[str]
    ) -> List[Dict[str, Any]]:
        """
        调用 AI 标记单个分块

        Args:
            all_paragraphs: 完整段落列表
            chunk_start: 当前块起始索引
            chunk_end: 当前块结束索引
            context_paragraphs: 用于获取上下文的段落列表

        Returns:
            标记结果列表
        """
        chunk_paragraphs = all_paragraphs[chunk_start:chunk_end]

        # 获取上下文
        context_before_paras = all_paragraphs[
            max(0, chunk_start - self.config.context_overlap):chunk_start
        ]
        context_after_paras = all_paragraphs[
            chunk_end:min(len(all_paragraphs), chunk_end + self.config.context_overlap)
        ]

        # 构建上下文字符串
        context_before = ""
        if context_before_paras:
            context_before = "【上下文参考（仅供理解，不需标记）】\n"
            for i, p in enumerate(context_before_paras):
                context_before += f"[上文-{len(context_before_paras) - i}] {p[:150]}...\n" if len(p) > 150 else f"[上文-{len(context_before_paras) - i}] {p}\n"

        context_after = ""
        if context_after_paras:
            context_after = "\n【后续上下文（仅供理解，不需标记）】\n"
            for i, p in enumerate(context_after_paras):
                context_after += f"[下文+{i + 1}] {p[:150]}...\n" if len(p) > 150 else f"[下文+{i + 1}] {p}\n"

        # 构建待标记段落字符串
        paragraphs_str = ""
        for i, p in enumerate(chunk_paragraphs):
            global_idx = chunk_start + i
            display_text = p[:200] + "..." if len(p) > 200 else p
            paragraphs_str += f"[{global_idx}] {display_text}\n"

        # 构建完整提示词
        prompt = AI_CHUNK_MARKING_PROMPT.format(
            context_before=context_before,
            paragraphs=paragraphs_str,
            context_after=context_after,
        )

        # 调用 AI
        messages = [
            {"role": "system", "content": "你是一个专业的论文结构识别助手，只返回JSON格式结果，不要使用markdown代码块包裹。"},
            {"role": "user", "content": prompt}
        ]

        for retry in range(self.config.max_retries + 1):
            try:
                response = await self.ai_service.complete(messages)

                # 解析响应
                json_str = response.strip()
                if json_str.startswith("```json"):
                    json_str = json_str[7:]
                if json_str.startswith("```"):
                    json_str = json_str[3:]
                if json_str.endswith("```"):
                    json_str = json_str[:-3]
                json_str = json_str.strip()

                result = json.loads(json_str)

                if not isinstance(result, list):
                    raise ValueError("AI 返回结果不是列表格式")

                return result

            except (json.JSONDecodeError, ValueError) as e:
                if retry < self.config.max_retries:
                    continue
                raise e

        return []

    def identify_paragraph_type(self, text: str) -> str:
        """
        使用规则识别段落类型

        Args:
            text: 段落文本

        Returns:
            段落类型
        """
        text = text.strip()
        if not text:
            return "body"

        text_lower = text.lower()

        for para_type, patterns in STRUCTURE_PATTERNS.items():
            for pattern in patterns:
                check_text = text_lower if "en" in para_type.lower() else text
                if re.match(pattern, check_text, re.IGNORECASE):
                    return para_type

        return "body"

    def assemble_marked_text(self, paragraphs: List[ParagraphInfo]) -> str:
        """
        组装带标记的文本

        格式：
        <!-- wf:type=heading_1 -->
        第一章 绪论

        <!-- wf:type=body -->
        这是正文内容...
        """
        lines = []

        for para in paragraphs:
            # 特殊标记不添加类型标记
            if para.text in ('[[PAGEBREAK]]', '[[SECTIONBREAK]]', '---pagebreak---', '---sectionbreak---'):
                lines.append(para.text)
                lines.append('')
                continue

            # 添加类型标记
            ptype = para.paragraph_type or "body"
            marker = f"<!-- wf:type={ptype} -->"
            lines.append(marker)
            lines.append(para.text)
            lines.append('')

        return '\n'.join(lines).strip()

    def verify_integrity(
        self,
        original_text: str,
        marked_text: str
    ) -> Tuple[bool, List[Dict[str, Any]]]:
        """
        验证原文一致性

        Args:
            original_text: 原始文本
            marked_text: 带标记的文本

        Returns:
            (是否通过, 差异列表)
        """
        # 移除标记
        cleaned = re.sub(r'<!--\s*wf:[^>]+-->\s*', '', marked_text)

        # 归一化
        def normalize(text: str) -> str:
            text = text.replace('\r\n', '\n').replace('\r', '\n')
            text = re.sub(r'\n{3,}', '\n\n', text)
            text = text.strip()
            return text

        original_normalized = normalize(original_text)
        cleaned_normalized = normalize(cleaned)

        # 完全匹配检查
        if original_normalized == cleaned_normalized:
            return True, []

        # 分段比对，定位差异
        original_paragraphs = original_normalized.split('\n\n')
        cleaned_paragraphs = cleaned_normalized.split('\n\n')

        differences = []

        max_len = max(len(original_paragraphs), len(cleaned_paragraphs))
        for i in range(max_len):
            orig = original_paragraphs[i] if i < len(original_paragraphs) else ""
            clean = cleaned_paragraphs[i] if i < len(cleaned_paragraphs) else ""

            if orig != clean:
                differences.append({
                    "position": i,
                    "original": orig[:100] + "..." if len(orig) > 100 else orig,
                    "marked": clean[:100] + "..." if len(clean) > 100 else clean,
                })

        return False, differences

    def _is_likely_heading(self, text: str) -> bool:
        """判断是否可能是标题"""
        if not text:
            return False
        if len(text) > 100:
            return False
        if re.match(r'^[\d一二三四五六七八九十]+[、\.\s]', text):
            return True
        if re.match(r'^第[一二三四五六七八九十\d]+[章节]', text):
            return True
        return False

    def _compute_hash(self, text: str) -> str:
        """计算文本 hash"""
        normalized = text.replace('\r\n', '\n').replace('\r', '\n').strip()
        return hashlib.sha256(normalized.encode('utf-8')).hexdigest()[:16]
