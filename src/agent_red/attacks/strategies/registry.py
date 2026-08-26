from __future__ import annotations
import pdb
from dataclasses import dataclass
from typing import Any, Callable, Optional

from ..session import AttackSession
from ...custom_types import Sample, AttackStrategyConfig, PromptInjection
from .prompt_session import PromptInjectionSession, StaticPromptInjectionSession
from .generator import AdaptiveLLMGenerator
from .sample_registry import REGISTRY


DEFAULT_STRATEGY = "multi"


def _build_single_llm_session(sample: Sample, config: AttackStrategyConfig, channel: str, file_path: Optional[str] = None) -> PromptInjectionSession:
    """
    Build a single-shot LLM session (no feedback, one attempt only).
    Uses LLM to generate the attack but does not refine based on feedback.
    """
    generator = AdaptiveLLMGenerator(
        base_sample=sample,
        model=config.model,
        base_url=config.base_url,
        api_key=config.api_key,
        chat_generator=config.chat_generator,
    )
    
    return PromptInjectionSession(
        base_sample=sample,
        channel=channel,
        max_rounds=1,  # Single shot, no refinement
        generator=generator,
        file_path=file_path,
    )


def _build_multi_llm_session(sample: Sample, config: AttackStrategyConfig, channel: str, file_path: Optional[str] = None) -> PromptInjectionSession:
    """
    Build a multi-turn LLM session with feedback-based refinement.
    Uses LLM to generate, execute, and refine based on feedback.
    """
    generator = AdaptiveLLMGenerator(
        base_sample=sample,
        model=config.model,
        base_url=config.base_url,
        api_key=config.api_key,
        chat_generator=config.chat_generator,
    )
    
    return PromptInjectionSession(
        base_sample=sample,
        channel=channel,
        max_rounds=config.max_rounds,  # Multi-turn with feedback
        generator=generator,
        file_path=file_path,
    )


def _build_static_session(sample: Sample, config: AttackStrategyConfig, channel: str, file_path: Optional[str] = None) -> StaticPromptInjectionSession:
    """
    Build a static session without LLM generation.
    Uses pre-crafted injections from base_sample.prompt_injections without refinement.
    """
    return StaticPromptInjectionSession(
        base_sample=sample,
        channel=channel,
        max_rounds=1,
        file_path=file_path,
    )


def _build_reuse_session(sample: Sample, config: AttackStrategyConfig, channel: str, file_path: Optional[str] = None) -> AttackSession:
    """
    Build a session that reuses previously generated injections from the registry.
    If injections are found, it uses them for the FIRST attempt.
    If that fails, it proceeds with LLM-based generation/refinement (regular multi-turn).
    If not found, it falls back to the default multi-turn LLM session directly.
    """
    reused_sample = REGISTRY.get_sample(sample.id)
    
    # Check if we got a valid sample with injections
    if reused_sample and reused_sample.prompt_injections:
        # Use same generator setup as multi-turn
        generator = AdaptiveLLMGenerator(
            base_sample=reused_sample,
            model=config.model,
            base_url=config.base_url,
            api_key=config.api_key,
            chat_generator=config.chat_generator,
        )

        # Return a PromptInjectionSession but with reuse_first=True
        # This means attempt 0 will use `injections` as-is, subsequent attempts will generate.
        return PromptInjectionSession(
            base_sample=reused_sample,
            channel=channel,
            max_rounds=config.max_rounds,
            generator=generator,
            file_path=file_path,
            reuse_first=True,
        )
    
    # Fallback to standard multi session if no history found
    return _build_multi_llm_session(sample, config, channel, file_path)


def _parse_strategy(strategy_name: str | None) -> tuple[str, str]:
    """
    Parse strategy name into (method, channel).
    Format: "{method}_{channel}" or just "{method}" (uses config.mode for channel)
    Examples:
      - "single" → ("single", config.mode)
      - "multi" → ("multi", config.mode)
      - "static" → ("static", config.mode)
      - "reuse" → ("reuse", config.mode)
      - "single_cursorrules" → ("single", "cursorrules")
      - "multi_file" → ("multi", "file")
      - "reuse_input" → ("reuse", "input")
    """
    name = (strategy_name or DEFAULT_STRATEGY).lower().strip()
    
    # Predefined single-method strategies
    if name in ["single", "multi", "static", "reuse"]:
        return (name, "")  # Empty channel means use config.mode
    
    # Composite strategies: "{method}_{channel}"
    if "_" in name:
        parts = name.split("_", 1)
        method, channel = parts[0], parts[1]
        if method in ["single", "multi", "static", "reuse"]:
            return (method, channel)
    
    # Unknown format, default to multi with config.mode
    return (DEFAULT_STRATEGY, "")


def build_attack_session(strategy_name: str | None, sample: Sample, config: AttackStrategyConfig) -> AttackSession:
    """
    Build an attack session based on strategy name, channel, and config.
    
    Strategy names can be:
    - "{method}": Uses config.mode as channel
      - "single" → single-shot LLM on config.mode channel
      - "multi" → multi-turn LLM on config.mode channel (default)
      - "static" → static injection on config.mode channel
    - "{method}_{channel}": Explicit method and channel
      - "multi_cursorrules" → multi-turn LLM on .cursorrules
      - "single_file" → single-shot LLM on file injection
      - "static_input" → static injection on input channel
    """
    method, explicit_channel = _parse_strategy(strategy_name)
    
    # Determine channel: use explicit channel or fall back to config.mode
    channel = explicit_channel or config.mode
    
    # Handle .cursorrules file path
    file_path = None
    if channel == "cursorrules":
        file_path = ".cursorrules"
    
    # Build session based on method
    if method == "single":
        return _build_single_llm_session(sample, config, channel=channel, file_path=file_path)
    
    if method == "multi":
        return _build_multi_llm_session(sample, config, channel=channel, file_path=file_path)
    
    if method == "static":
        return _build_static_session(sample, config, channel=channel, file_path=file_path)

    if method == "reuse":
        return _build_reuse_session(sample, config, channel=channel, file_path=file_path)
    
    # Default fallback
    return _build_multi_llm_session(sample, config, channel=channel, file_path=file_path)
