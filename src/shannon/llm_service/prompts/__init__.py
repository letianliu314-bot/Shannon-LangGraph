from shannon.llm_service.prompts.decomposition import (
    COMMON_DECOMPOSITION_SUFFIX_TEMPLATE,
    DEEP_STRATEGY_GUIDANCE,
    GENERAL_PLANNING_IDENTITY,
    PROMPT_VERSION,
    build_decompose_system_prompt,
)
from shannon.llm_service.prompts.execution import (
    INTERPRETATION_PROMPT_GENERAL,
    INTERPRETATION_PROMPT_SOURCES,
    RESEARCH_MODE_INSTRUCTION,
    should_use_source_format,
)
from shannon.llm_service.prompts.research_supervisor import (
    DOMAIN_ANALYSIS_HINT,
    RESEARCH_SUPERVISOR_IDENTITY,
)

# 中文注释：提示词导出
__all__ = [
    "PROMPT_VERSION",
    "RESEARCH_SUPERVISOR_IDENTITY",
    "DOMAIN_ANALYSIS_HINT",
    "GENERAL_PLANNING_IDENTITY",
    "COMMON_DECOMPOSITION_SUFFIX_TEMPLATE",
    "DEEP_STRATEGY_GUIDANCE",
    "build_decompose_system_prompt",
    "RESEARCH_MODE_INSTRUCTION",
    "INTERPRETATION_PROMPT_SOURCES",
    "INTERPRETATION_PROMPT_GENERAL",
    "should_use_source_format",
]
