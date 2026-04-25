"""
文章格式检测服务（Format Checker）

功能：
1. 检测 Markdown 格式是否符合规范
2. 基于规则自动识别段落类型（无需 AI）
3. 检测标题层级是否连续
4. 检测必要结构是否存在（摘要、关键词等）
5. 提示用户不符合格式的部分
6. 支持宽松/严格两种检测模式
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple


class CheckMode(str, Enum):
    """检测模式"""
    LOOSE = "loose"      # 宽松模式：只检测关键格式问题
    STRICT = "strict"    # 严格模式：所有不规范格式都报错


class IssueSeverity(str, Enum):
    """问题严重程度"""
    ERROR = "error"      # 错误：必须修复
    WARNING = "warning"  # 警告：建议修复
    INFO = "info"        # 提示：可选修复


class IssueType(str, Enum):
    """问题类型"""
    HEADING_SKIP = "heading_skip"           # 标题层级跳跃
    HEADING_DUPLICATE = "heading_duplicate" # 重复标题层级
    MISSING_ABSTRACT = "missing_abstract"   # 缺少摘要
    MISSING_KEYWORDS = "missing_keywords"   # 缺少关键词
    INVALID_LIST = "invalid_list"           # 无效列表格式
    EMPTY_PARAGRAPH = "empty_paragraph"     # 空段落
    LONG_PARAGRAPH = "long_paragraph"       # 段落过长
    REFERENCE_FORMAT = "reference_format"   # 参考文献格式问题
    EXISTING_MARKER = "existing_marker"     # 已有 wf:type 标记


@dataclass
class FormatIssue:
    """格式问题"""
    line: int                    # 行号（从1开始）
    paragraph_index: int         # 段落索引
    issue_type: IssueType        # 问题类型
    severity: IssueSeverity      # 严重程度
    message: str                 # 问题描述
    suggestion: str              # 修复建议
    content_preview: str = ""    # 内容预览（前50字符）


@dataclass
class ParagraphInfo:
    """段落信息"""
    index: int                              # 段落索引
    text: str                               # 段落文本
    line_start: int                         # 起始行号
    line_end: int                           # 结束行号
    paragraph_type: str = "body"            # 段落类型
    confidence: float = 1.0                 # 识别置信度
    is_auto_detected: bool = True           # 是否自动检测


@dataclass
class FormatCheckResult:
    """格式检测结果"""
    success: bool
    is_valid: bool                              # 是否通过检测
    mode: CheckMode                             # 检测模式
    issues: List[FormatIssue] = field(default_factory=list)
    paragraphs: List[ParagraphInfo] = field(default_factory=list)
    marked_text: str = ""                       # 带标记的文本
    type_statistics: Dict[str, int] = field(default_factory=dict)
    original_hash: str = ""
    error: Optional[str] = None


# 段落类型定义
PARAGRAPH_TYPES = {
    "title_cn": "中文标题",
    "title_en": "英文标题",
    "abstract_cn": "中文摘要",
    "abstract_en": "英文摘要",
    "keywords_cn": "中文关键词",
    "keywords_en": "英文关键词",
    "heading_1": "一级标题",
    "heading_2": "二级标题",
    "heading_3": "三级标题",
    "heading_4": "四级标题",
    "heading_5": "五级标题",
    "heading_6": "六级标题",
    "body": "正文",
    "reference": "参考文献",
    "acknowledgement": "致谢",
    "figure_caption": "图题",
    "table_caption": "表题",
    "list_item": "列表项",
    "toc": "目录",
    "code_block": "代码块",
    "blockquote": "引用块",
}


# 段落类型识别规则（按优先级排序）
DETECTION_RULES = [
    # Markdown 标题检测（必须按层级顺序，从高到低匹配）
    ("heading_6", [r"^######\s+.+$"]),
    ("heading_5", [r"^#####\s+.+$"]),
    ("heading_4", [r"^####\s+.+$"]),
    ("heading_3", [r"^###\s+.+$"]),
    ("heading_2", [r"^##\s+.+$"]),
    ("heading_1", [r"^#\s+.+$"]),

    # 代码块
    ("code_block", [r"^```", r"^~~~"]),

    # 引用块
    ("blockquote", [r"^>\s+"]),

    # 中文摘要/关键词
    ("abstract_cn", [
        r"^摘\s*要[:：]?\s*",
        r"^【摘\s*要】",
        r"^内容摘要[:：]?\s*",
    ]),
    ("keywords_cn", [
        r"^关键词[:：]?\s*",
        r"^关键字[:：]?\s*",
        r"^【关键词】",
    ]),

    # 英文摘要/关键词
    ("abstract_en", [
        r"^[Aa]bstract[:：]?\s*",
        r"^[Ss]ummary[:：]?\s*",
    ]),
    ("keywords_en", [
        r"^[Kk]ey\s*[Ww]ords[:：]?\s*",
        r"^[Kk]eywords[:：]?\s*",
    ]),

    # 致谢
    ("acknowledgement", [
        r"^致\s*谢",
        r"^谢\s*辞",
        r"^[Aa]cknowledgement",
    ]),

    # 参考文献标题
    ("heading_1", [
        r"^参考文献\s*$",
        r"^[Rr]eferences\s*$",
    ]),

    # 参考文献条目
    ("reference", [
        r"^\[\d+\]\s*.+",           # [1] 格式
        r"^\d+\.\s+[A-Z].+",        # 1. Author 格式
    ]),

    # 图表标题
    ("figure_caption", [
        r"^图\s*\d+[\.．:：]?\s*.+",
        r"^[Ff]ig\.?\s*\d+[\.．:：]?\s*.+",
        r"^[Ff]igure\s*\d+[\.．:：]?\s*.+",
    ]),
    ("table_caption", [
        r"^表\s*\d+[\.．:：]?\s*.+",
        r"^[Tt]ab\.?\s*\d+[\.．:：]?\s*.+",
        r"^[Tt]able\s*\d+[\.．:：]?\s*.+",
    ]),

    # 目录
    ("toc", [
        r"^目\s*录\s*$",
        r"^[Cc]ontents?\s*$",
        r"^[Tt]able\s+of\s+[Cc]ontents?\s*$",
    ]),

    # 中文章节标题（数字编号）
    ("heading_1", [
        r"^第[一二三四五六七八九十百]+[章节]\s+",
        r"^[一二三四五六七八九十]+[、\.．]\s*",
        r"^\d+\s+[^\d\.\s].{2,}$",  # "1 材料与方法" 格式
    ]),
    ("heading_2", [
        r"^[（\(][一二三四五六七八九十]+[）\)]\s*",
        r"^\d+[\.．]\d+\s+",         # "1.1 xxx" 格式
    ]),
    ("heading_3", [
        r"^\d+[\.．]\d+[\.．]\d+\s+",  # "1.1.1 xxx" 格式
    ]),

    # 列表项
    ("list_item", [
        r"^[-*+]\s+.+",              # 无序列表
        r"^\d+[\.）\)]\s+.+",        # 有序列表
        r"^[a-zA-Z][\.）\)]\s+.+",   # 字母列表
    ]),
]


class FormatChecker:
    """文章格式检测器"""

    def __init__(self, mode: CheckMode = CheckMode.LOOSE):
        self.mode = mode

    def check(self, text: str) -> FormatCheckResult:
        """
        执行格式检测

        Args:
            text: 原始文章文本

        Returns:
            FormatCheckResult 检测结果
        """
        if not text or not text.strip():
            return FormatCheckResult(
                success=False,
                is_valid=False,
                mode=self.mode,
                error="文章内容为空"
            )

        try:
            # 计算原文 hash
            original_hash = self._compute_hash(text)

            # 分割段落并记录行号
            paragraphs = self._split_paragraphs_with_lines(text)

            if not paragraphs:
                return FormatCheckResult(
                    success=False,
                    is_valid=False,
                    mode=self.mode,
                    error="无法分割段落",
                    original_hash=original_hash
                )

            # 自动识别段落类型
            self._detect_paragraph_types(paragraphs)

            # 检测格式问题
            issues = self._check_issues(paragraphs, text)

            # 根据模式过滤问题
            if self.mode == CheckMode.LOOSE:
                issues = [i for i in issues if i.severity == IssueSeverity.ERROR]

            # 生成带标记的文本
            marked_text = self._generate_marked_text(paragraphs)

            # 统计类型分布
            type_stats = self._compute_type_statistics(paragraphs)

            # 判断是否通过
            has_errors = any(i.severity == IssueSeverity.ERROR for i in issues)

            return FormatCheckResult(
                success=True,
                is_valid=not has_errors,
                mode=self.mode,
                issues=issues,
                paragraphs=paragraphs,
                marked_text=marked_text,
                type_statistics=type_stats,
                original_hash=original_hash
            )

        except Exception as e:
            return FormatCheckResult(
                success=False,
                is_valid=False,
                mode=self.mode,
                error=f"格式检测失败: {str(e)}"
            )

    def _split_paragraphs_with_lines(self, text: str) -> List[ParagraphInfo]:
        """
        分割段落并记录行号
        """
        # 标准化换行符
        text = text.replace('\r\n', '\n').replace('\r', '\n')

        lines = text.split('\n')
        paragraphs = []
        current_para_lines = []
        current_start = 1

        for i, line in enumerate(lines, start=1):
            stripped = line.strip()

            if not stripped:
                # 空行：结束当前段落
                if current_para_lines:
                    para_text = '\n'.join(current_para_lines)
                    paragraphs.append(ParagraphInfo(
                        index=len(paragraphs),
                        text=para_text,
                        line_start=current_start,
                        line_end=i - 1
                    ))
                    current_para_lines = []
                current_start = i + 1
            else:
                if not current_para_lines:
                    current_start = i
                current_para_lines.append(stripped)

        # 处理最后一个段落
        if current_para_lines:
            para_text = '\n'.join(current_para_lines)
            paragraphs.append(ParagraphInfo(
                index=len(paragraphs),
                text=para_text,
                line_start=current_start,
                line_end=len(lines)
            ))

        return paragraphs

    def _detect_paragraph_types(self, paragraphs: List[ParagraphInfo]) -> None:
        """
        自动检测段落类型
        """
        for para in paragraphs:
            text = para.text.strip()

            # 检查是否已有 wf:type 标记
            marker_match = re.match(r'^<!--\s*wf:type=(\w+)\s*-->', text)
            if marker_match:
                para.paragraph_type = marker_match.group(1)
                para.is_auto_detected = False
                para.confidence = 1.0
                # 移除标记，保留实际内容
                para.text = re.sub(r'^<!--\s*wf:type=\w+\s*-->\s*', '', text)
                continue

            # 按规则检测
            detected = False
            for ptype, patterns in DETECTION_RULES:
                for pattern in patterns:
                    if re.match(pattern, text, re.IGNORECASE | re.MULTILINE):
                        para.paragraph_type = ptype
                        para.confidence = 0.9
                        detected = True
                        break
                if detected:
                    break

            if not detected:
                para.paragraph_type = "body"
                para.confidence = 0.7

    def _check_issues(
        self,
        paragraphs: List[ParagraphInfo],
        original_text: str
    ) -> List[FormatIssue]:
        """
        检测格式问题
        """
        issues = []

        # 检查标题层级
        issues.extend(self._check_heading_hierarchy(paragraphs))

        # 检查必要结构
        issues.extend(self._check_required_structure(paragraphs))

        # 检查段落问题
        issues.extend(self._check_paragraph_issues(paragraphs))

        # 检查参考文献格式
        issues.extend(self._check_reference_format(paragraphs))

        # 检查已有标记
        issues.extend(self._check_existing_markers(original_text))

        return issues

    def _check_heading_hierarchy(self, paragraphs: List[ParagraphInfo]) -> List[FormatIssue]:
        """
        检查标题层级是否连续
        """
        issues = []
        last_heading_level = 0

        # 标题类型到层级的映射
        heading_level_map = {
            "heading_1": 1,
            "heading_2": 2,
            "heading_3": 3,
            "heading_4": 4,
            "heading_5": 5,
            "heading_6": 6,
        }

        for para in paragraphs:
            current_level = heading_level_map.get(para.paragraph_type, 0)

            if current_level > 0:
                # 检查是否跳级（如从一级直接到三级）
                if last_heading_level > 0 and current_level > last_heading_level + 1:
                    issues.append(FormatIssue(
                        line=para.line_start,
                        paragraph_index=para.index,
                        issue_type=IssueType.HEADING_SKIP,
                        severity=IssueSeverity.WARNING,
                        message=f"标题层级跳跃：从{last_heading_level}级直接到{current_level}级",
                        suggestion=f"建议添加{last_heading_level + 1}级标题作为过渡，或调整当前标题层级",
                        content_preview=para.text[:50]
                    ))

                last_heading_level = current_level

        return issues

    def _check_required_structure(self, paragraphs: List[ParagraphInfo]) -> List[FormatIssue]:
        """
        检查必要结构是否存在
        """
        issues = []
        types_found = {p.paragraph_type for p in paragraphs}

        # 检查是否有摘要（中文或英文）
        has_abstract = "abstract_cn" in types_found or "abstract_en" in types_found
        if not has_abstract:
            issues.append(FormatIssue(
                line=1,
                paragraph_index=0,
                issue_type=IssueType.MISSING_ABSTRACT,
                severity=IssueSeverity.INFO,
                message="未检测到摘要部分",
                suggestion="建议添加以'摘要：'或'Abstract:'开头的段落",
                content_preview=""
            ))

        # 检查是否有关键词
        has_keywords = "keywords_cn" in types_found or "keywords_en" in types_found
        if not has_keywords:
            issues.append(FormatIssue(
                line=1,
                paragraph_index=0,
                issue_type=IssueType.MISSING_KEYWORDS,
                severity=IssueSeverity.INFO,
                message="未检测到关键词部分",
                suggestion="建议添加以'关键词：'或'Keywords:'开头的段落",
                content_preview=""
            ))

        return issues

    def _check_paragraph_issues(self, paragraphs: List[ParagraphInfo]) -> List[FormatIssue]:
        """
        检查段落级别问题
        """
        issues = []

        for para in paragraphs:
            text = para.text.strip()

            # 检查空段落（只有空白字符）
            if not text:
                issues.append(FormatIssue(
                    line=para.line_start,
                    paragraph_index=para.index,
                    issue_type=IssueType.EMPTY_PARAGRAPH,
                    severity=IssueSeverity.WARNING,
                    message="发现空段落",
                    suggestion="建议删除空段落或添加内容",
                    content_preview=""
                ))

            # 检查段落过长（超过1000字符）
            elif len(text) > 1000 and para.paragraph_type == "body":
                issues.append(FormatIssue(
                    line=para.line_start,
                    paragraph_index=para.index,
                    issue_type=IssueType.LONG_PARAGRAPH,
                    severity=IssueSeverity.INFO,
                    message=f"段落较长（{len(text)}字符）",
                    suggestion="可考虑拆分为多个段落以提高可读性",
                    content_preview=text[:50] + "..."
                ))

        return issues

    def _check_reference_format(self, paragraphs: List[ParagraphInfo]) -> List[FormatIssue]:
        """
        检查参考文献格式
        """
        issues = []
        ref_paragraphs = [p for p in paragraphs if p.paragraph_type == "reference"]

        if not ref_paragraphs:
            return issues

        # 检查编号连续性
        expected_num = 1
        for para in ref_paragraphs:
            match = re.match(r'^\[(\d+)\]', para.text)
            if match:
                actual_num = int(match.group(1))
                if actual_num != expected_num:
                    issues.append(FormatIssue(
                        line=para.line_start,
                        paragraph_index=para.index,
                        issue_type=IssueType.REFERENCE_FORMAT,
                        severity=IssueSeverity.WARNING,
                        message=f"参考文献编号不连续：期望[{expected_num}]，实际[{actual_num}]",
                        suggestion=f"请检查参考文献编号顺序",
                        content_preview=para.text[:50]
                    ))
                expected_num = actual_num + 1

        return issues

    def _check_existing_markers(self, text: str) -> List[FormatIssue]:
        """
        检查是否已有 wf:type 标记
        """
        issues = []
        lines = text.split('\n')

        for i, line in enumerate(lines, start=1):
            if re.search(r'<!--\s*wf:type=\w+\s*-->', line):
                issues.append(FormatIssue(
                    line=i,
                    paragraph_index=-1,
                    issue_type=IssueType.EXISTING_MARKER,
                    severity=IssueSeverity.INFO,
                    message="检测到已有的 wf:type 标记",
                    suggestion="已有标记将被保留，无需处理",
                    content_preview=line[:50]
                ))

        return issues

    def _generate_marked_text(self, paragraphs: List[ParagraphInfo]) -> str:
        """
        生成带标记的文本
        """
        lines = []

        for para in paragraphs:
            # 特殊标记不添加类型标记
            if para.text in ('[[PAGEBREAK]]', '[[SECTIONBREAK]]'):
                lines.append(para.text)
                lines.append('')
                continue

            # 添加类型标记
            marker = f"<!-- wf:type={para.paragraph_type} -->"
            lines.append(marker)
            lines.append(para.text)
            lines.append('')

        return '\n'.join(lines).strip()

    def _compute_type_statistics(self, paragraphs: List[ParagraphInfo]) -> Dict[str, int]:
        """
        计算段落类型统计
        """
        stats: Dict[str, int] = {}
        for para in paragraphs:
            ptype = para.paragraph_type
            stats[ptype] = stats.get(ptype, 0) + 1
        return stats

    def _compute_hash(self, text: str) -> str:
        """
        计算文本 hash
        """
        normalized = text.replace('\r\n', '\n').replace('\r', '\n').strip()
        return hashlib.sha256(normalized.encode('utf-8')).hexdigest()[:16]


def check_format(
    text: str,
    mode: str = "loose"
) -> FormatCheckResult:
    """
    便捷函数：检测文章格式

    Args:
        text: 原始文章文本
        mode: 检测模式 ("loose" 或 "strict")

    Returns:
        FormatCheckResult 检测结果
    """
    check_mode = CheckMode.STRICT if mode == "strict" else CheckMode.LOOSE
    checker = FormatChecker(mode=check_mode)
    return checker.check(text)
