"""
DocumentAST: 结构化内容表示（确定性编译输入）。
"""
from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field, field_validator


InlineType = Literal["text", "bold", "italic", "underline", "superscript", "subscript", "code"]


class Inline(BaseModel):
    type: InlineType
    text: str


BlockType = Literal[
    "heading",
    "paragraph",
    "list",
    "table",
    "code_block",
    "figure",
    "page_break",
    "section_break",
    "bibliography",
]


class HeadingBlock(BaseModel):
    type: Literal["heading"] = "heading"
    level: int = Field(..., ge=1, le=8)
    text: str


class ParagraphBlock(BaseModel):
    type: Literal["paragraph"] = "paragraph"
    text: Optional[str] = None
    inlines: Optional[List[Inline]] = None

    @field_validator("text")
    @classmethod
    def _text_or_inlines(cls, v, info):
        # allow None if inlines provided
        return v


class CodeBlock(BaseModel):
    """代码块，用于表示 Markdown 中的 fenced code block。"""
    type: Literal["code_block"] = "code_block"
    text: str
    language: Optional[str] = None


class ListItem(BaseModel):
    inlines: List[Inline]


class ListBlock(BaseModel):
    type: Literal["list"] = "list"
    ordered: bool = False
    items: List[ListItem]


class TableBlock(BaseModel):
    type: Literal["table"] = "table"
    rows: List[List[str]]
    rows_inlines: Optional[List[List[List[Inline]]]] = None  # 富文本表格行
    caption: Optional[str] = None


class FigureBlock(BaseModel):
    type: Literal["figure"] = "figure"
    path: str
    caption: Optional[str] = None


class PageBreakBlock(BaseModel):
    type: Literal["page_break"] = "page_break"


class SectionBreakBlock(BaseModel):
    type: Literal["section_break"] = "section_break"
    kind: Literal["next_page"] = "next_page"


class BibliographyBlock(BaseModel):
    type: Literal["bibliography"] = "bibliography"
    items: List[str]


Block = Union[
    HeadingBlock,
    ParagraphBlock,
    CodeBlock,
    ListBlock,
    TableBlock,
    FigureBlock,
    PageBreakBlock,
    SectionBreakBlock,
    BibliographyBlock,
]


class DocumentMeta(BaseModel):
    title_cn: Optional[str] = None
    title_en: Optional[str] = None
    author: Optional[str] = None
    major: Optional[str] = None
    tutor: Optional[str] = None
    extra: Dict[str, Any] = Field(default_factory=dict)


class DocumentAST(BaseModel):
    meta: DocumentMeta = Field(default_factory=DocumentMeta)
    blocks: List[Block]
