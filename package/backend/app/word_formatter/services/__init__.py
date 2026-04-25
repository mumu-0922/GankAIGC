"""
word_formatter 服务层
"""

from .ast_generator import (
    parse_markdown_to_ast,
    parse_plaintext_heuristic,
    parse_marked_text_to_ast,
    identify_paragraph_type,
    VALID_MARKER_TYPES,
)
from .spec_generator import (
    build_generic_spec,
    builtin_specs,
    ai_generate_spec,
    validate_custom_spec,
    export_spec_to_json,
    get_spec_schema,
)
from .template_generator import (
    generate_reference_docx,
    patch_reference_docx,
)
from .renderer import (
    render_docx,
    RenderOptions,
)
from .validator import validate_docx
from .fixer import (
    fix_docx,
    build_patch_from_report,
    apply_patch,
)
from .compiler import (
    compile_document,
    CompileOptions,
    CompileResult,
    CompileProgress,
    CompilePhase,
    InputFormat,
    detect_input_format,
)
from .job_manager import (
    JobManager,
    Job,
    JobType,
    JobStatus,
    JobProgress,
    get_job_manager,
    init_job_manager,
)
from .preprocessor import (
    ArticlePreprocessor,
    PreprocessConfig,
    PreprocessProgress,
    PreprocessResult,
    PreprocessPhase,
    ParagraphInfo,
    VALID_PARAGRAPH_TYPES,
)
from .format_checker import (
    FormatChecker,
    FormatCheckResult,
    FormatIssue,
    CheckMode,
    IssueSeverity,
    IssueType,
    ParagraphInfo as FormatParagraphInfo,
    check_format,
    PARAGRAPH_TYPES,
)

__all__ = [
    # AST Generator
    "parse_markdown_to_ast",
    "parse_plaintext_heuristic",
    "parse_marked_text_to_ast",
    "identify_paragraph_type",
    "VALID_MARKER_TYPES",
    # Spec Generator
    "build_generic_spec",
    "builtin_specs",
    "ai_generate_spec",
    "validate_custom_spec",
    "export_spec_to_json",
    "get_spec_schema",
    # Template Generator
    "generate_reference_docx",
    "patch_reference_docx",
    # Renderer
    "render_docx",
    "RenderOptions",
    # Validator
    "validate_docx",
    # Fixer
    "fix_docx",
    "build_patch_from_report",
    "apply_patch",
    # Compiler
    "compile_document",
    "CompileOptions",
    "CompileResult",
    "CompileProgress",
    "CompilePhase",
    "InputFormat",
    "detect_input_format",
    # Job Manager
    "JobManager",
    "Job",
    "JobType",
    "JobStatus",
    "JobProgress",
    "get_job_manager",
    "init_job_manager",
    # Preprocessor
    "ArticlePreprocessor",
    "PreprocessConfig",
    "PreprocessProgress",
    "PreprocessResult",
    "PreprocessPhase",
    "ParagraphInfo",
    "VALID_PARAGRAPH_TYPES",
    # Format Checker
    "FormatChecker",
    "FormatCheckResult",
    "FormatIssue",
    "CheckMode",
    "IssueSeverity",
    "IssueType",
    "FormatParagraphInfo",
    "check_format",
    "PARAGRAPH_TYPES",
]
