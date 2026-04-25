"""
Text/Markdown → DocumentAST（确定性解析为主；AI 可插拔）。

支持：
- Markdown（推荐）：# / ## / ###，列表、表格、图片语法（可选）
- 轻量标题：行首 1、1.1、1.1.1 识别为标题层级
- AI 辅助：识别纯文本中的段落类型（标题/摘要/正文等）
"""
from __future__ import annotations

import re
import json
from typing import Any, Dict, List, Optional, Tuple

import mistune

from ..models.ast import (
    BibliographyBlock,
    CodeBlock,
    DocumentAST,
    DocumentMeta,
    FigureBlock,
    HeadingBlock,
    Inline,
    ListBlock,
    ListItem,
    ParagraphBlock,
    PageBreakBlock,
    SectionBreakBlock,
    TableBlock,
)


_FRONT_MATTER_RE = re.compile(r"^\s*---\s*$", re.M)


def _parse_front_matter(text: str) -> Tuple[Dict[str, str], str]:
    """
    支持非常轻量的 YAML front matter（不依赖 pyyaml）：
    ---
    key: value
    key2: value2
    ---
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text
    meta: Dict[str, str] = {}
    i = 1
    while i < len(lines):
        if lines[i].strip() == "---":
            body = "\n".join(lines[i + 1 :])
            return meta, body
        if ":" in lines[i]:
            k, v = lines[i].split(":", 1)
            meta[k.strip()] = v.strip()
        i += 1
    # no closing ---; treat as normal text
    return {}, text


def _inlines_from_children(children: List[Dict[str, Any]]) -> List[Inline]:
    inlines: List[Inline] = []
    for ch in children:
        t = ch.get("type")
        if t == "text":
            inlines.append(Inline(type="text", text=ch.get("raw", "") or ch.get("text", "")))
        elif t == "strong":
            txt = "".join(_collect_text(ch))
            inlines.append(Inline(type="bold", text=txt))
        elif t == "emphasis":
            txt = "".join(_collect_text(ch))
            inlines.append(Inline(type="italic", text=txt))
        elif t == "inline_code":
            inlines.append(Inline(type="code", text=ch.get("raw", "") or ch.get("text", "")))
        elif t == "linebreak":
            inlines.append(Inline(type="text", text="\n"))
        else:
            # fallback as text
            txt = "".join(_collect_text(ch))
            if txt:
                inlines.append(Inline(type="text", text=txt))
    return inlines


def _collect_text(node: Any) -> List[str]:
    """收集节点中的所有纯文本内容。"""
    if isinstance(node, list):
        out: List[str] = []
        for n in node:
            out.extend(_collect_text(n))
        return out
    if isinstance(node, str):
        return [node]
    if not isinstance(node, dict):
        return []
    if "raw" in node and isinstance(node["raw"], str):
        return [node["raw"]]
    if "text" in node and isinstance(node["text"], str):
        return [node["text"]]
    out = []
    for c in node.get("children", []) or []:
        out.extend(_collect_text(c))
    return out


def _inlines_from_table_cell(cell: Any) -> List[Inline]:
    """从表格单元格中提取 Inline 列表，保留富文本格式。"""
    if isinstance(cell, list):
        return _inlines_from_children(cell)
    if isinstance(cell, dict):
        children = cell.get("children", []) or []
        if children:
            return _inlines_from_children(children)
        # 单个节点作为列表处理
        return _inlines_from_children([cell])
    # 兜底：作为纯文本
    return [Inline(type="text", text="".join(_collect_text(cell)))]


def parse_markdown_to_ast(text: str) -> DocumentAST:
    meta_dict, body = _parse_front_matter(text)
    # 注意：已移除 _normalize_markdown_lists 调用
    # 该函数会将 "6.2"、"1）" 等标题编号误转换为列表项，
    # 导致 Word 输出中产生重复的递增序号
    meta = DocumentMeta(
        title_cn=meta_dict.get("title_cn"),
        title_en=meta_dict.get("title_en"),
        author=meta_dict.get("author"),
        major=meta_dict.get("major"),
        tutor=meta_dict.get("tutor"),
        extra={k: v for k, v in meta_dict.items() if k not in {"title_cn", "title_en", "author", "major", "tutor"}},
    )

    md = mistune.create_markdown(renderer="ast", plugins=["strikethrough", "table"])
    nodes = md(body)

    blocks: List[Any] = []

    for n in nodes:
        t = n.get("type")
        if t == "heading":
            level = int(n.get("level", 1))
            txt = "".join(_collect_text(n))
            blocks.append(HeadingBlock(level=level, text=txt))
        elif t == "paragraph":
            children = n.get("children", []) or []

            # page/section break markers
            plain_text = "".join(_collect_text(n)).strip()
            if plain_text in {"<!-- pagebreak -->", "<!--PAGEBREAK-->", "[[PAGEBREAK]]", "\\f"}:
                blocks.append(PageBreakBlock())
                continue
            if plain_text in {"<!-- sectionbreak -->", "<!--SECTIONBREAK-->", "[[SECTIONBREAK]]"}:
                blocks.append(SectionBreakBlock(kind="next_page"))
                continue

            # image-only paragraph -> figure block
            if len(children) == 1 and children[0].get("type") == "image":
                img = children[0]
                blocks.append(FigureBlock(path=img.get("src") or "", caption=img.get("alt") or None))
                continue

            inlines = _inlines_from_children(children)
            # collapse plain text if possible
            plain = "".join(i.text for i in inlines) if all(i.type == "text" for i in inlines) else None
            blocks.append(ParagraphBlock(text=plain, inlines=None if plain is not None else inlines))
        elif t == "list":
            ordered = bool(n.get("ordered", False))
            items: List[ListItem] = []
            for item in n.get("children", []) or []:
                # item: {'type': 'list_item', 'children': [...]}
                # collect paragraphs inside
                texts: List[Inline] = []
                for c in item.get("children", []) or []:
                    if c.get("type") == "paragraph":
                        texts.extend(_inlines_from_children(c.get("children", []) or []))
                if not texts:
                    texts = [Inline(type="text", text="".join(_collect_text(item)))]
                items.append(ListItem(inlines=texts))
            blocks.append(ListBlock(ordered=ordered, items=items))
        elif t == "block_code":
            # 处理代码块（fenced code block）
            language = (n.get("info") or "").strip() or None
            code_text = n.get("raw") or n.get("text") or ""
            blocks.append(CodeBlock(text=code_text, language=language))
        elif t == "table":
            rows: List[List[str]] = []
            rows_inlines: List[List[List[Inline]]] = []
            header = n.get("header", []) or []
            if header:
                header_plain: List[str] = []
                header_inlines: List[List[Inline]] = []
                for cell in header:
                    cell_inlines = _inlines_from_table_cell(cell)
                    header_inlines.append(cell_inlines)
                    header_plain.append("".join(i.text for i in cell_inlines))
                rows.append(header_plain)
                rows_inlines.append(header_inlines)
            for row in n.get("cells", []) or []:
                row_plain: List[str] = []
                row_inlines: List[List[Inline]] = []
                for cell in row:
                    cell_inlines = _inlines_from_table_cell(cell)
                    row_inlines.append(cell_inlines)
                    row_plain.append("".join(i.text for i in cell_inlines))
                rows.append(row_plain)
                rows_inlines.append(row_inlines)
            blocks.append(TableBlock(rows=rows, rows_inlines=rows_inlines if rows_inlines else None))
        elif t == "image":
            # Mistune 在 paragraph 中出现 image；这里不一定到达
            path = n.get("src") or ""
            caption = n.get("alt") or None
            blocks.append(FigureBlock(path=path, caption=caption))
        else:
            # fallback: try extract as paragraph
            txt = "".join(_collect_text(n)).strip()
            if txt:
                blocks.append(ParagraphBlock(text=txt))

    # bibliography convenience: if存在一级标题"参考文献"，后续以 [n] 开头的段落合并为 bibliography block
    blocks2: List[Any] = []
    in_ref = False
    bib_items: List[str] = []
    for b in blocks:
        if isinstance(b, HeadingBlock) and b.level == 1 and b.text.strip() in {"参考文献", "References"}:
            in_ref = True
            blocks2.append(b)
            continue
        if in_ref and isinstance(b, ParagraphBlock):
            text = (b.text or "").strip()
            if re.match(r"^\[\d+\]", text):
                bib_items.append(text)
                continue
            if bib_items:
                blocks2.append(BibliographyBlock(items=bib_items))
                bib_items = []
            blocks2.append(b)
            in_ref = False
            continue
        blocks2.append(b)
    if bib_items:
        blocks2.append(BibliographyBlock(items=bib_items))

    return DocumentAST(meta=meta, blocks=blocks2)


# ============ Markdown 标记解析器 ============

# 支持的段落类型
VALID_MARKER_TYPES = frozenset({
    "title_cn", "title_en",
    "abstract_cn", "abstract_en",
    "keywords_cn", "keywords_en",
    "heading_1", "heading_2", "heading_3",
    "body",
    "reference", "acknowledgement",
    "figure_caption", "table_caption",
})

# 匹配 <!-- wf:type=xxx --> 格式的标记
_MARKER_RE = re.compile(r"<!--\s*wf:type\s*=\s*(?P<type>[a-zA-Z0-9_]+)\s*-->")


def parse_marked_text_to_ast(text: str) -> DocumentAST:
    """
    解析带 <!-- wf:type=xxx --> 标记的文本。

    标记格式：
        <!-- wf:type=heading_1 -->
        第一章 绪论

    或同一行：
        <!-- wf:type=body --> 这是正文内容...

    如果段落没有标记，则使用 identify_paragraph_type() 规则识别。

    Args:
        text: 带标记的文本

    Returns:
        DocumentAST 文档结构
    """
    meta_dict, body = _parse_front_matter(text)
    meta = DocumentMeta(
        title_cn=meta_dict.get("title_cn"),
        title_en=meta_dict.get("title_en"),
        author=meta_dict.get("author"),
        major=meta_dict.get("major"),
        tutor=meta_dict.get("tutor"),
        extra={k: v for k, v in meta_dict.items()
               if k not in {"title_cn", "title_en", "author", "major", "tutor"}},
    )

    lines = body.splitlines()
    blocks: List[Any] = []
    para_buf: List[str] = []
    pending_type: Optional[str] = None

    def flush_para() -> None:
        """将缓冲区内容作为一个段落处理"""
        nonlocal para_buf, pending_type
        if not para_buf:
            pending_type = None
            return

        para_text = "\n".join(para_buf).strip()
        para_buf = []

        if not para_text:
            pending_type = None
            return

        # 确定段落类型：优先使用标记，否则使用规则识别
        para_type = pending_type if pending_type in VALID_MARKER_TYPES else identify_paragraph_type(para_text)
        pending_type = None

        # 根据类型生成对应的 AST 块
        block = _create_block_from_type(para_text, para_type, meta)
        if block:
            if isinstance(block, list):
                blocks.extend(block)
            else:
                blocks.append(block)

    for line in lines:
        stripped = line.strip()

        # 空行触发段落刷新
        if not stripped:
            if para_buf:
                flush_para()
            continue

        # 分页/分节标记
        if stripped in {"[[PAGEBREAK]]", "---pagebreak---"}:
            flush_para()
            blocks.append(PageBreakBlock())
            continue
        if stripped in {"[[SECTIONBREAK]]", "---sectionbreak---"}:
            flush_para()
            blocks.append(SectionBreakBlock(kind="next_page"))
            continue

        # 检查是否包含 wf:type 标记
        match = _MARKER_RE.search(line)
        if match:
            # 发现新标记，先刷新之前的段落
            if para_buf:
                flush_para()

            marker_type = match.group("type")
            pending_type = marker_type if marker_type in VALID_MARKER_TYPES else None

            # 移除标记后检查是否还有内容
            cleaned = _MARKER_RE.sub("", line).strip()
            if cleaned:
                para_buf.append(cleaned)
            continue

        # 普通行加入缓冲区
        para_buf.append(line)

    # 处理最后的缓冲区
    flush_para()

    # 后处理：合并参考文献条目
    blocks = _merge_bibliography_blocks(blocks)

    return DocumentAST(meta=meta, blocks=blocks)


def _create_block_from_type(
    para_text: str,
    para_type: str,
    meta: DocumentMeta
) -> Any:
    """
    根据段落类型创建对应的 AST 块。

    Args:
        para_text: 段落文本
        para_type: 段落类型
        meta: 文档元数据（用于提取标题等）

    Returns:
        AST 块或块列表
    """
    # 标题类型
    if para_type == "title_cn":
        meta.title_cn = para_text
        return HeadingBlock(level=1, text=para_text)

    if para_type == "title_en":
        meta.title_en = para_text
        return HeadingBlock(level=1, text=para_text)

    # 摘要类型
    if para_type in ("abstract_cn", "abstract_en"):
        is_cn = "cn" in para_type
        # 检查是否以"摘要"或"Abstract"开头
        if "摘要" in para_text[:10] or "abstract" in para_text[:20].lower():
            heading = HeadingBlock(level=1, text="摘要" if is_cn else "Abstract")
            content = re.sub(r"^(摘\s*要|abstract)[:：\s]*", "", para_text, flags=re.IGNORECASE)
            if content:
                return [heading, ParagraphBlock(text=content)]
            return heading
        return ParagraphBlock(text=para_text)

    # 关键词类型
    if para_type in ("keywords_cn", "keywords_en"):
        is_cn = "cn" in para_type
        if "关键词" in para_text[:10] or "关键字" in para_text[:10] or "keyword" in para_text[:20].lower():
            heading = HeadingBlock(level=1, text="关键词" if is_cn else "Key words")
            content = re.sub(r"^(关键词|关键字|key\s*words)[:：\s]*", "", para_text, flags=re.IGNORECASE)
            if content:
                return [heading, ParagraphBlock(text=content)]
            return heading
        return ParagraphBlock(text=para_text)

    # 各级标题
    if para_type == "heading_1":
        return HeadingBlock(level=1, text=para_text)
    if para_type == "heading_2":
        return HeadingBlock(level=2, text=para_text)
    if para_type == "heading_3":
        return HeadingBlock(level=3, text=para_text)

    # 参考文献标题
    if para_type == "reference":
        if "参考文献" in para_text or "references" in para_text.lower():
            return HeadingBlock(level=1, text="参考文献")
        return ParagraphBlock(text=para_text)

    # 致谢标题
    if para_type == "acknowledgement":
        if "致谢" in para_text or "谢辞" in para_text or "acknowledgement" in para_text.lower():
            return HeadingBlock(level=1, text="致谢")
        return ParagraphBlock(text=para_text)

    # 默认作为正文段落
    return ParagraphBlock(text=para_text)


def _merge_bibliography_blocks(blocks: List[Any]) -> List[Any]:
    """
    合并参考文献条目为 BibliographyBlock。

    在"参考文献"标题后，将以 [n] 开头的段落合并为一个 BibliographyBlock。
    """
    result: List[Any] = []
    in_ref = False
    bib_items: List[str] = []

    for block in blocks:
        # 检测参考文献标题
        if isinstance(block, HeadingBlock) and block.level == 1:
            if block.text.strip() in {"参考文献", "References"}:
                in_ref = True
                result.append(block)
                continue

        # 在参考文献区域内处理
        if in_ref and isinstance(block, ParagraphBlock):
            text = (block.text or "").strip()
            if re.match(r"^\[\d+\]", text):
                bib_items.append(text)
                continue
            # 遇到非参考文献条目，结束收集
            if bib_items:
                result.append(BibliographyBlock(items=bib_items))
                bib_items = []
            result.append(block)
            in_ref = False
            continue

        result.append(block)

    # 处理末尾的参考文献条目
    if bib_items:
        result.append(BibliographyBlock(items=bib_items))

    return result


_HEADING_NUM_RE = re.compile(r"^\s*(\d+)([\.．](\d+))*([\.．](\d+))*\s+(.+)$")


def parse_plaintext_heuristic(text: str) -> DocumentAST:
    """
    非 Markdown 输入的兜底：按行扫描：
    - 1 / 1.1 / 1.1.1 / 1．1．1 开头的行 → heading
    - 空行分段 → paragraph
    """
    meta, body = _parse_front_matter(text)
    lines = body.splitlines()
    blocks: List[Any] = []
    para_buf: List[str] = []

    def flush_para():
        nonlocal para_buf
        if para_buf:
            t = "\n".join(para_buf).strip()
            if t:
                blocks.append(ParagraphBlock(text=t))
            para_buf = []

    for line in lines:
        if not line.strip():
            flush_para()
            continue
        if line.strip() in {"[[PAGEBREAK]]", "---pagebreak---"}:
            flush_para()
            blocks.append(PageBreakBlock())
            continue
        if line.strip() in {"[[SECTIONBREAK]]", "---sectionbreak---"}:
            flush_para()
            blocks.append(SectionBreakBlock(kind="next_page"))
            continue
        m = _HEADING_NUM_RE.match(line)
        if m:
            flush_para()
            # count levels by number of separators
            prefix = line.split()[0]
            sep_count = prefix.count(".") + prefix.count("．")
            level = min(1 + sep_count, 3)
            title = line.split(None, 1)[1].strip() if len(line.split(None, 1)) > 1 else line.strip()
            blocks.append(HeadingBlock(level=level, text=title))
        else:
            para_buf.append(line)
    flush_para()

    dm = DocumentMeta(
        title_cn=meta.get("title_cn"),
        title_en=meta.get("title_en"),
        author=meta.get("author"),
        major=meta.get("major"),
        tutor=meta.get("tutor"),
        extra={k: v for k, v in meta.items() if k not in {"title_cn", "title_en", "author", "major", "tutor"}},
    )
    return DocumentAST(meta=dm, blocks=blocks)


# ============ AI 辅助识别功能 ============

# 论文结构关键词识别规则
STRUCTURE_PATTERNS = {
    "title_cn": [
        r"^[\u4e00-\u9fa5]{2,50}$",  # 纯中文标题
    ],
    "title_en": [
        r"^[A-Z][a-zA-Z\s\-:]+$",  # 英文标题
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


def identify_paragraph_type(text: str) -> str:
    """
    使用规则识别段落类型。
    返回: heading_1, heading_2, heading_3, abstract_cn, abstract_en,
          keywords_cn, keywords_en, reference, acknowledgement, body
    """
    text = text.strip()
    if not text:
        return "body"

    text_lower = text.lower()

    for para_type, patterns in STRUCTURE_PATTERNS.items():
        for pattern in patterns:
            if re.match(pattern, text_lower if "en" in para_type.lower() else text, re.IGNORECASE):
                return para_type

    return "body"


async def ai_identify_paragraph_types(
    paragraphs: List[str],
    ai_service: Any,
    model: str = None
) -> List[Dict[str, str]]:
    """
    使用 AI 识别段落类型。

    参数:
        paragraphs: 段落文本列表
        ai_service: AI 服务实例
        model: 使用的模型（可选）

    返回:
        [{"text": "段落文本", "type": "heading_1|body|abstract|..."}]
    """
    # 如果段落数量为 0，直接返回空列表
    if not paragraphs:
        print("[WORD-FORMATTER] AI 段落识别跳过：无段落输入", flush=True)
        return []

    print("\n" + "=" * 80, flush=True)
    print("[WORD-FORMATTER] AI 段落类型识别开始", flush=True)
    print(f"[WORD-FORMATTER] 待识别段落数量: {len(paragraphs)}", flush=True)

    # 构建识别提示词
    prompt = """你是一个论文结构识别专家。请分析以下段落，判断每个段落的类型。

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

待分析的段落：
"""

    # 限制段落数量避免过长
    max_paragraphs = min(len(paragraphs), 50)
    for i in range(max_paragraphs):
        para = paragraphs[i]
        prompt += f"\n[{i}] {para[:200]}"  # 限制每段长度

    try:
        messages = [
            {"role": "system", "content": "你是一个专业的论文结构识别助手，只返回JSON格式结果，不要使用markdown代码块包裹。"},
            {"role": "user", "content": prompt}
        ]

        # 详细日志：请求信息
        print(f"[WORD-FORMATTER] AI 请求消息数: {len(messages)}", flush=True)
        print(f"[WORD-FORMATTER] 系统提示词长度: {len(messages[0]['content'])} 字符", flush=True)
        print(f"[WORD-FORMATTER] 用户提示词长度: {len(messages[1]['content'])} 字符", flush=True)
        print("[WORD-FORMATTER] 正在调用 AI 服务...", flush=True)

        response = await ai_service.complete(messages)

        # 详细日志：响应信息
        print(f"[WORD-FORMATTER] AI 响应长度: {len(response)} 字符", flush=True)

        # 解析 AI 返回的 JSON
        # 移除可能的 markdown 代码块标记
        json_str = response.strip()
        original_response = json_str  # 保留原始响应用于日志
        if json_str.startswith("```json"):
            json_str = json_str[7:]
            print("[WORD-FORMATTER] 检测到 ```json 标记，已移除", flush=True)
        if json_str.startswith("```"):
            json_str = json_str[3:]
            print("[WORD-FORMATTER] 检测到 ``` 标记，已移除", flush=True)
        if json_str.endswith("```"):
            json_str = json_str[:-3]
            print("[WORD-FORMATTER] 检测到结尾 ``` 标记，已移除", flush=True)
        json_str = json_str.strip()

        result = json.loads(json_str)

        # 验证返回结果格式
        if not isinstance(result, list):
            raise ValueError("AI 返回结果不是列表格式")

        print(f"[WORD-FORMATTER] JSON 解析成功，识别到 {len(result)} 个结果项", flush=True)

        # 构建返回结果
        identified = []
        valid_types = {
            "title_cn", "title_en", "abstract_cn", "abstract_en",
            "keywords_cn", "keywords_en", "heading_1", "heading_2",
            "heading_3", "body", "reference", "acknowledgement",
            "figure_caption", "table_caption"
        }

        type_counts = {}  # 统计各类型数量
        for i, para in enumerate(paragraphs):
            para_type = "body"
            for item in result:
                if isinstance(item, dict) and item.get("index") == i:
                    detected_type = item.get("type", "body")
                    # 验证类型是否有效
                    if detected_type in valid_types:
                        para_type = detected_type
                    else:
                        print(f"[WORD-FORMATTER] 警告：段落[{i}] 检测到无效类型 '{detected_type}'，回退到 'body'", flush=True)
                    break
            identified.append({"text": para, "type": para_type})
            type_counts[para_type] = type_counts.get(para_type, 0) + 1

        # 输出类型统计
        print("[WORD-FORMATTER] 段落类型统计:", flush=True)
        for ptype, count in sorted(type_counts.items(), key=lambda x: -x[1]):
            print(f"  - {ptype}: {count} 个", flush=True)
        print("=" * 80 + "\n", flush=True)

        return identified

    except json.JSONDecodeError as e:
        # JSON 解析失败时回退到规则识别
        print("=" * 80, flush=True)
        print(f"[WORD-FORMATTER] ⚠️ AI 识别 JSON 解析失败: {e}", flush=True)
        print(f"[WORD-FORMATTER] 原始响应内容: {response[:500] if 'response' in dir() else 'N/A'}...", flush=True)
        print("[WORD-FORMATTER] 回退到规则识别模式", flush=True)
        print("=" * 80 + "\n", flush=True)
        return [{"text": para, "type": identify_paragraph_type(para)} for para in paragraphs]
    except Exception as e:
        # AI 识别失败时回退到规则识别
        import traceback
        print("=" * 80, flush=True)
        print(f"[WORD-FORMATTER] ⚠️ AI 识别失败: {e}", flush=True)
        print(f"[WORD-FORMATTER] 异常类型: {type(e).__name__}", flush=True)
        print(f"[WORD-FORMATTER] 堆栈跟踪:\n{traceback.format_exc()}", flush=True)
        print("[WORD-FORMATTER] 回退到规则识别模式", flush=True)
        print("=" * 80 + "\n", flush=True)
        return [{"text": para, "type": identify_paragraph_type(para)} for para in paragraphs]


def parse_plaintext_with_ai_types(
    text: str,
    paragraph_types: List[Dict[str, str]]
) -> DocumentAST:
    """
    根据 AI 识别的段落类型构建 DocumentAST。

    参数:
        text: 原始文本
        paragraph_types: AI 识别的段落类型列表

    返回:
        DocumentAST
    """
    meta = DocumentMeta()
    blocks: List[Any] = []

    for item in paragraph_types:
        para_text = item["text"].strip()
        para_type = item["type"]

        if not para_text:
            continue

        # 提取元数据
        if para_type == "title_cn":
            meta.title_cn = para_text
            blocks.append(HeadingBlock(level=1, text=para_text))
        elif para_type == "title_en":
            meta.title_en = para_text
            blocks.append(HeadingBlock(level=1, text=para_text))
        elif para_type in ("abstract_cn", "abstract_en"):
            # 摘要作为标题 + 正文
            if "摘要" in para_text[:10] or "abstract" in para_text[:20].lower():
                blocks.append(HeadingBlock(level=1, text="摘要" if "cn" in para_type else "Abstract"))
                # 去掉标题部分
                content = re.sub(r"^(摘\s*要|abstract)[:：\s]*", "", para_text, flags=re.IGNORECASE)
                if content:
                    blocks.append(ParagraphBlock(text=content))
            else:
                blocks.append(ParagraphBlock(text=para_text))
        elif para_type in ("keywords_cn", "keywords_en"):
            # 关键词作为标题 + 正文
            if "关键词" in para_text[:10] or "关键字" in para_text[:10] or "keyword" in para_text[:20].lower():
                blocks.append(HeadingBlock(level=1, text="关键词" if "cn" in para_type else "Key words"))
                content = re.sub(r"^(关键词|关键字|key\s*words)[:：\s]*", "", para_text, flags=re.IGNORECASE)
                if content:
                    blocks.append(ParagraphBlock(text=content))
            else:
                blocks.append(ParagraphBlock(text=para_text))
        elif para_type == "heading_1":
            blocks.append(HeadingBlock(level=1, text=para_text))
        elif para_type == "heading_2":
            blocks.append(HeadingBlock(level=2, text=para_text))
        elif para_type == "heading_3":
            blocks.append(HeadingBlock(level=3, text=para_text))
        elif para_type == "reference":
            if "参考文献" in para_text or "references" in para_text.lower():
                blocks.append(HeadingBlock(level=1, text="参考文献"))
            else:
                blocks.append(ParagraphBlock(text=para_text))
        elif para_type == "acknowledgement":
            if "致谢" in para_text or "谢辞" in para_text or "acknowledgement" in para_text.lower():
                blocks.append(HeadingBlock(level=1, text="致谢"))
            else:
                blocks.append(ParagraphBlock(text=para_text))
        else:
            # body 或未知类型
            blocks.append(ParagraphBlock(text=para_text))

    return DocumentAST(meta=meta, blocks=blocks)
