"""
规范生成器（Spec Generator）

功能：
1. 内置论文规范（通用中文论文格式）
2. 自定义 JSON 导入与校验
3. AI 根据用户要求生成规范模板
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

from ..models.stylespec import (
    FontMapping,
    ForbiddenDirectFormatting,
    MarginMM,
    PageNumberingSpec,
    PageSpec,
    StructureSpec,
    StyleDef,
    StyleParagraph,
    StyleRun,
    StyleSpec,
)
from ..utils.chinese import DEFAULT_CHINESE_FONTS, DEFAULT_ENGLISH_FONTS, pt


logger = logging.getLogger(__name__)


# ============ 常量定义 ============

# 中文字号对应表 (中文名称 -> pt 值)
CHINESE_FONT_SIZE_MAP = {
    "初号": 42,
    "小初": 36,
    "一号": 26,
    "小一": 24,
    "二号": 22,
    "小二": 18,
    "三号": 16,
    "小三": 15,
    "四号": 14,
    "小四": 12,
    "五号": 10.5,
    "小五": 9,
    "六号": 7.5,
    "小六": 6.5,
    "七号": 5.5,
    "八号": 5,
}

# 中文字体名称映射
CHINESE_FONT_MAP = {
    "宋体": "SimSun",
    "黑体": "SimHei",
    "仿宋": "FangSong",
    "仿宋体": "FangSong",
    "楷体": "KaiTi",
    "楷书": "KaiTi",
    "微软雅黑": "Microsoft YaHei",
    "华文宋体": "STSong",
    "华文黑体": "STHeiti",
    "华文仿宋": "STFangsong",
    "华文楷体": "STKaiti",
}

# 英文字体名称
ENGLISH_FONT_MAP = {
    "Times New Roman": "Times New Roman",
    "Arial": "Arial",
    "Calibri": "Calibri",
}

# 内置模板信息
BUILTIN_TEMPLATES = {
    "通用论文（首行缩进）": {
        "id": "generic_cn_indent",
        "description": "正文段落首行缩进2字符，适用于大多数学术论文和毕业论文",
        "first_line_indent": True,
    },
    "通用论文（无缩进）": {
        "id": "generic_cn_noindent",
        "description": "正文段落无首行缩进，段落间有额外间距，适用于部分期刊格式",
        "first_line_indent": False,
    },
}


def _font(ch: str, en: str) -> FontMapping:
    """创建字体映射"""
    return FontMapping(eastAsia=ch, ascii=en, hAnsi=en)


def build_generic_spec(first_line_indent: bool = True) -> StyleSpec:
    """
    构建通用中文论文格式规范。

    根据毕业论文格式规范优化：
    - 标题：3号黑体居中
    - 作者信息：小四仿宋体
    - 摘要/关键词：五号宋体
    - 目录标题：4号黑体居中
    - 一级标题：仿宋体四号（如"1 材料与方法"）
    - 二级标题：黑体小四号（如"1.1 xxx"）
    - 三级标题：仿宋体小四号（如"1.1.1 xxx"）
    - 正文：小四宋体

    参数:
        first_line_indent: 正文是否首行缩进2字符（默认True）

    返回:
        StyleSpec 对象
    """
    # 页面设置
    page = PageSpec(
        size="A4",
        margins_mm=MarginMM(top=25.4, bottom=25.4, left=31.7, right=31.7, binding=0),
        header_mm=15,
        footer_mm=15,
    )

    # 字体
    song = DEFAULT_CHINESE_FONTS["songti"]      # 宋体
    hei = DEFAULT_CHINESE_FONTS["heiti"]        # 黑体
    fang = DEFAULT_CHINESE_FONTS["fangsong"]    # 仿宋
    kai = DEFAULT_CHINESE_FONTS["kaiti"]        # 楷体
    times = DEFAULT_ENGLISH_FONTS["times"]      # Times New Roman

    styles = {}

    def add_style(
        style_id: str,
        name: str,
        ch_font: str,
        en_font: str,
        size_pt: float,
        bold: bool = False,
        align: str = "justify",
        before: float = 0,
        after: float = 0,
        before_lines: float | None = None,
        after_lines: float | None = None,
        first_indent_chars: float = 0,
        keep_with_next: bool = False,
        is_heading: bool = False,
        outline_level: int | None = None,
        line_spacing_rule: str = "single",
        line_spacing: float | None = None,
    ):
        styles[style_id] = StyleDef(
            style_id=style_id,
            name=name,
            based_on=None,
            is_heading=is_heading,
            outline_level=outline_level,
            run=StyleRun(
                bold=bold,
                italic=False,
                underline=False,
                size_pt=size_pt,
                font=_font(ch_font, en_font),
            ),
            paragraph=StyleParagraph(
                alignment=align,
                line_spacing_rule=line_spacing_rule,
                line_spacing=line_spacing,
                space_before_pt=before,
                space_after_pt=after,
                space_before_lines=before_lines,
                space_after_lines=after_lines,
                first_line_indent_chars=first_indent_chars,
                hanging_indent_chars=0,
                keep_with_next=keep_with_next,
                keep_lines=False,
                page_break_before=False,
                widows_control=True,
            ),
        )

    # 前置部分标题（摘要、目录等）
    add_style(
        "FrontHeading", "前置标题",
        hei, times, pt("四号"),
        bold=False, align="center",
        before=12, after=12
    )

    # 中文标题 - 3号黑体居中
    add_style(
        "TitleCN", "中文标题",
        hei, times, pt("三号"),
        bold=False, align="center",
        before=0, after=12
    )

    # 英文标题 - 3号 Times New Roman 居中
    add_style(
        "TitleEN", "英文标题",
        times, times, pt("三号"),
        bold=False, align="center",
        before=0, after=12
    )

    # 作者信息/元信息 - 小四仿宋体居中
    add_style(
        "MetaLine", "作者信息",
        fang, times, pt("小四"),
        bold=False, align="center",
        before=0, after=6
    )

    # 中文摘要正文 - 五号宋体
    add_style(
        "AbstractBody", "摘要正文",
        song, times, pt("五号"),
        bold=False, align="justify",
        before=0, after=0,
        first_indent_chars=2
    )

    # 中文关键词正文 - 五号宋体
    add_style(
        "KeywordsBody", "关键词正文",
        song, times, pt("五号"),
        bold=False, align="justify",
        before=0, after=0,
        first_indent_chars=0
    )

    # 目录标题 - 4号黑体居中
    add_style(
        "TocTitle", "目录标题",
        hei, times, pt("四号"),
        bold=False, align="center",
        before=12, after=12
    )

    # 正文 - 小四宋体，1.5倍行距
    body_indent = 2 if first_line_indent else 0
    add_style(
        "Body", "正文",
        song, times, pt("小四"),
        bold=False, align="justify",
        before=0, after=0,
        first_indent_chars=body_indent,
        line_spacing_rule="1.5"
    )

    # 列表项
    add_style(
        "ListBullet", "无序列表",
        song, times, pt("小四"),
        bold=False, align="justify",
        before=0, after=0,
        first_indent_chars=0
    )

    add_style(
        "ListNumber", "有序列表",
        song, times, pt("小四"),
        bold=False, align="justify",
        before=0, after=0,
        first_indent_chars=0
    )

    # 页码 - 五号宋体居中
    add_style(
        "PageNumber", "页码",
        song, times, pt("五号"),
        bold=False, align="center",
        before=0, after=0,
        first_indent_chars=0
    )

    # 一级标题 - 仿宋体四号，左对齐（如"1 材料与方法"）
    add_style(
        "H1", "一级标题",
        fang, times, pt("四号"),
        bold=False, align="left",
        before=0, after=0,
        before_lines=0.5, after_lines=0.5,
        first_indent_chars=0,
        keep_with_next=True,
        is_heading=True, outline_level=0
    )

    # 二级标题 - 黑体小四号，左对齐（如"1.1 xxx"）
    add_style(
        "H2", "二级标题",
        hei, times, pt("小四"),
        bold=False, align="left",
        before=0, after=0,
        before_lines=0.3, after_lines=0.3,
        first_indent_chars=0,
        keep_with_next=True,
        is_heading=True, outline_level=1
    )

    # 三级标题 - 仿宋体小四号，左对齐（如"1.1.1 xxx"）
    add_style(
        "H3", "三级标题",
        fang, times, pt("小四"),
        bold=False, align="left",
        before=0, after=0,
        before_lines=0.2, after_lines=0.2,
        first_indent_chars=0,
        keep_with_next=True,
        is_heading=True, outline_level=2
    )

    # 图题 - 小五黑体居中
    add_style(
        "FigureCaption", "图题",
        hei, times, pt("小五"),
        bold=False, align="center",
        before=6, after=6
    )

    # 表题 - 小五黑体居中
    add_style(
        "TableTitle", "表题",
        hei, times, pt("小五"),
        bold=False, align="center",
        before=6, after=6
    )

    # 表内容 - 六号宋体居中
    add_style(
        "TableText", "表格内容",
        song, times, pt("六号"),
        bold=False, align="center",
        before=0, after=0
    )

    # 参考文献 - 五号宋体
    add_style(
        "Reference", "参考文献",
        song, times, pt("五号"),
        bold=False, align="justify",
        before=0, after=0,
        first_indent_chars=0
    )

    # 致谢正文
    add_style(
        "AcknowledgementBody", "致谢正文",
        song, times, pt("小四"),
        bold=False, align="justify",
        before=0, after=0,
        first_indent_chars=2,
        line_spacing_rule="1.5"
    )

    # 结构规范
    structure = StructureSpec(
        required_h1_titles=["摘要", "Abstract", "引言", "致谢", "参考文献"],
        toc_max_level=3,
    )

    # 模板名称
    template_name = "通用论文（首行缩进）" if first_line_indent else "通用论文（无缩进）"
    template_notes = (
        "正文首行缩进2字符，适用于大多数学术论文和毕业论文"
        if first_line_indent
        else "正文无首行缩进，段落间有额外间距，适用于部分期刊格式"
    )

    spec = StyleSpec(
        meta={
            "name": template_name,
            "version": "2.0",
            "notes": template_notes,
        },
        page=page,
        styles=styles,
        numbering=None,
        structure=structure,
        forbidden_direct_formatting=ForbiddenDirectFormatting(),
        page_numbering=PageNumberingSpec(
            enabled=True,
            front_format="romanUpper",
            front_start=1,
            main_format="decimal",
            main_start=1,
            show_in_footer=True,
            footer_alignment="center"
        ),
        auto_prefix_abstract_keywords=True,
        auto_number_figures_tables=True,
    )
    return spec


def builtin_specs() -> Dict[str, StyleSpec]:
    """
    获取所有内置规范

    返回:
        字典，键为模板中文名称，值为 StyleSpec 对象
    """
    return {
        "通用论文（首行缩进）": build_generic_spec(first_line_indent=True),
        "通用论文（无缩进）": build_generic_spec(first_line_indent=False),
    }


def get_builtin_template_info() -> Dict[str, Dict]:
    """
    获取内置模板的信息（用于前端展示）

    返回:
        字典，包含模板名称、描述等信息
    """
    return BUILTIN_TEMPLATES


# ============ AI 生成规范模板功能 ============

AI_SPEC_GENERATION_PROMPT = """你是一个专业的中国学术论文排版专家。请根据用户的要求生成论文排版规范模板。

【用户要求】
{requirements}

【输出要求】
请生成一个 JSON 格式的规范模板，严格遵循以下结构：

{{
    "meta": {{
        "name": "规范名称",
        "version": "1.0",
        "notes": "规范说明"
    }},
    "page": {{
        "size": "A4",
        "margins_mm": {{
            "top": 页边距上(mm，常见值: 25.4),
            "bottom": 页边距下(mm，常见值: 25.4),
            "left": 页边距左(mm，常见值: 31.7),
            "right": 页边距右(mm，常见值: 31.7),
            "binding": 装订线(mm，默认0)
        }},
        "header_mm": 页眉距离(mm，常见值: 15),
        "footer_mm": 页脚距离(mm，常见值: 15)
    }},
    "styles": {{
        "TitleCN": {{
            "style_id": "TitleCN",
            "name": "中文标题",
            "is_heading": false,
            "run": {{
                "bold": false,
                "italic": false,
                "underline": false,
                "size_pt": 字号(pt值),
                "font": {{
                    "eastAsia": "中文字体名(如SimHei)",
                    "ascii": "英文字体名(如Times New Roman)",
                    "hAnsi": "英文字体名(如Times New Roman)"
                }}
            }},
            "paragraph": {{
                "alignment": "center|left|right|justify",
                "line_spacing_rule": "single|1.5|double|exact",
                "line_spacing": null,
                "space_before_pt": 段前间距(pt),
                "space_after_pt": 段后间距(pt),
                "first_line_indent_chars": 首行缩进字符数
            }}
        }},
        "Body": {{ ... }},
        "H1": {{ ... }},
        "H2": {{ ... }},
        "H3": {{ ... }},
        "AbstractBody": {{ ... }},
        "KeywordsBody": {{ ... }},
        "Reference": {{ ... }},
        "FigureCaption": {{ ... }},
        "TableTitle": {{ ... }}
    }},
    "structure": {{
        "required_h1_titles": ["摘要", "Abstract", "引言", "致谢", "参考文献"],
        "toc_max_level": 3
    }}
}}

【中文字号对应表（必须使用）】
- 初号: 42pt    - 小初: 36pt
- 一号: 26pt    - 小一: 24pt
- 二号: 22pt    - 小二: 18pt
- 三号: 16pt    - 小三: 15pt
- 四号: 14pt    - 小四: 12pt
- 五号: 10.5pt  - 小五: 9pt
- 六号: 7.5pt   - 小六: 6.5pt

【字体名称对应（必须使用标准名称）】
中文字体:
- 宋体 → SimSun
- 黑体 → SimHei
- 仿宋 → FangSong
- 楷体 → KaiTi
- 微软雅黑 → Microsoft YaHei

英文字体:
- Times New Roman → Times New Roman
- Arial → Arial

【常见论文格式参考】
1. 毕业论文格式:
   - 标题: 三号黑体(16pt, SimHei)居中
   - 作者: 小四仿宋(12pt, FangSong)居中
   - 摘要/关键词: 五号宋体(10.5pt, SimSun)
   - 一级标题: 四号仿宋(14pt, FangSong)
   - 二级标题: 小四黑体(12pt, SimHei)
   - 三级标题: 小四仿宋(12pt, FangSong)
   - 正文: 小四宋体(12pt, SimSun)，首行缩进2字符
   - 参考文献: 五号宋体(10.5pt, SimSun)

2. 页边距常见设置:
   - 上下: 2.54cm (25.4mm)
   - 左右: 3.17cm (31.7mm)
   - 装订线: 0 或 0.5cm

【重要提示】
1. 只返回 JSON，不要任何其他文字
2. 确保 JSON 格式正确，所有字符串用双引号
3. 数值不要加引号
4. 必须包含所有必要的样式: TitleCN, Body, H1, H2, H3, AbstractBody, KeywordsBody, Reference
"""


async def ai_generate_spec(
    requirements: str,
    ai_service: Any,
    model: str = None
) -> StyleSpec:
    """
    使用 AI 根据用户要求生成规范模板。

    参数:
        requirements: 用户的规范要求描述
        ai_service: AI 服务实例
        model: 使用的模型（可选）

    返回:
        StyleSpec 对象

    抛出:
        ValueError: 如果生成失败
    """
    logger.info("=" * 60)
    logger.info("[SPEC-GENERATOR] AI 规范生成开始")
    logger.info(f"[SPEC-GENERATOR] 用户需求长度: {len(requirements)} 字符")
    logger.info(f"[SPEC-GENERATOR] 用户需求预览: {requirements[:200]}...")

    prompt = AI_SPEC_GENERATION_PROMPT.format(requirements=requirements)

    messages = [
        {
            "role": "system",
            "content": (
                "你是一个专业的中国学术论文排版规范生成助手。"
                "你必须严格按照要求生成 JSON 格式的规范模板。"
                "只返回有效的 JSON，不要任何额外的解释或注释。"
            )
        },
        {"role": "user", "content": prompt}
    ]

    logger.info(f"[SPEC-GENERATOR] 提示词长度: {len(prompt)} 字符")
    logger.info("[SPEC-GENERATOR] 正在调用 AI 服务...")

    try:
        response = await ai_service.complete(messages)

        logger.info(f"[SPEC-GENERATOR] AI 响应长度: {len(response)} 字符")

        # 清理并解析 JSON
        json_str = _clean_json_response(response)
        spec_dict = json.loads(json_str)

        logger.info("[SPEC-GENERATOR] JSON 解析成功")
        logger.info(f"[SPEC-GENERATOR] 规范名称: {spec_dict.get('meta', {}).get('name', 'Unknown')}")
        logger.info(f"[SPEC-GENERATOR] 样式数量: {len(spec_dict.get('styles', {}))}")

        # 验证并构建 StyleSpec
        spec = StyleSpec.model_validate(spec_dict)

        logger.info("[SPEC-GENERATOR] 规范验证成功")
        logger.info("=" * 60)

        return spec

    except json.JSONDecodeError as e:
        logger.error(f"[SPEC-GENERATOR] JSON 解析失败: {e}")
        logger.error(f"[SPEC-GENERATOR] 原始响应: {response[:500] if 'response' in dir() else 'N/A'}...")
        raise ValueError(f"AI 返回的规范格式不正确，请重试: {e}")

    except Exception as e:
        logger.error(f"[SPEC-GENERATOR] 规范生成失败: {e}", exc_info=True)
        raise ValueError(f"生成规范失败: {e}")


def _clean_json_response(response: str) -> str:
    """
    清理 AI 返回的 JSON 响应

    移除可能的 markdown 代码块标记等
    """
    json_str = response.strip()

    # 移除 markdown 代码块标记
    if json_str.startswith("```json"):
        json_str = json_str[7:]
    elif json_str.startswith("```"):
        json_str = json_str[3:]

    if json_str.endswith("```"):
        json_str = json_str[:-3]

    return json_str.strip()


def validate_custom_spec(spec_json: str) -> StyleSpec:
    """
    验证用户自定义的 JSON 规范。

    参数:
        spec_json: JSON 字符串

    返回:
        StyleSpec 对象

    抛出:
        ValueError: 如果 JSON 格式不正确或规范无效
    """
    try:
        spec_dict = json.loads(spec_json)
        spec = StyleSpec.model_validate(spec_dict)
        return spec
    except json.JSONDecodeError as e:
        raise ValueError(f"JSON 格式错误: {e}")
    except Exception as e:
        raise ValueError(f"规范验证失败: {e}")


def export_spec_to_json(spec: StyleSpec) -> str:
    """
    将规范导出为 JSON 字符串。

    参数:
        spec: StyleSpec 对象

    返回:
        格式化的 JSON 字符串
    """
    return spec.model_dump_json(indent=2, exclude_none=True)


def get_spec_schema() -> dict:
    """获取 StyleSpec 的 JSON Schema"""
    return StyleSpec.model_json_schema()
