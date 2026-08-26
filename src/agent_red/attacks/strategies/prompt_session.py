from __future__ import annotations
import pdb
from typing import Optional

from ..session import AttackAttempt, AttackFeedback, RegenerativeSessionBase
from ...custom_types import Sample, PromptInjection
from .generator import AdaptiveLLMGenerator
from .sample_registry import REGISTRY


class PromptInjectionSession(RegenerativeSessionBase):
    """
    LLM-based regenerative session that uses an AdaptiveLLMGenerator to craft payloads
    for a given channel (input, file, web, cursorrules).
    """

    def __init__(
        self,
        base_sample: Sample,
        channel: str = "input",
        max_rounds: int = 3,
        generator: Optional[AdaptiveLLMGenerator] = None,
        file_path: Optional[str] = None,
        reuse_first: bool = False,
    ):
        super().__init__(max_rounds=max_rounds)
        self.base_sample = base_sample
        self.channel = channel
        self.generator = generator or AdaptiveLLMGenerator(base_sample)
        self.file_path = file_path
        self.reuse_first = reuse_first

    def _normalize_injection_type(self, raw: str) -> str:
        if raw == "replace_match":
            return "replace"
        return raw or "append"

    def _build_attempt(self, sample: Optional[Sample], feedback: Optional[AttackFeedback], attempt_idx: int) -> AttackAttempt:
        metadata = {
            "attempt_idx": attempt_idx,
            "channel": self.channel,
        }

        # Collect updated injections and specs
        updated_injections = []
        merged_spec = {}

        # Use explicitly reused injections on first attempt if requested
        if self.reuse_first and attempt_idx == 0:
            if self.base_sample.prompt_injections:
                for injection in self.base_sample.prompt_injections:
                    updated_injections.append(injection)
                # Keep base sample metadata
                merged_spec = {} # No spec from generator
            else:
                 # Fallback if somehow reuse_first is True but no injections (shouldn't happen with correct registry logic)
                 pass
        else:
            # Process existing prompt_injections from base_sample
            for injection in self.base_sample.prompt_injections:
                spec = self.generator.generate(
                    feedback=feedback,
                    attempt_idx=attempt_idx,
                    channel=self.channel,
                    file_path=injection.target_file_path,
                )

                # If generator returns full spec with prompt_injections, consume them
                if isinstance(spec, dict) and spec.get("prompt_injections"):
                    for inj in spec.get("prompt_injections", []):
                        updated_injections.append(
                            PromptInjection(
                                target_file_path=inj.get("target_file_path") or injection.target_file_path,
                                injection_type=self._normalize_injection_type(inj.get("injection_type", "append")),
                                match_pattern=inj.get("match_pattern", ""),
                                payload_content=inj.get("payload_content", ""),
                            )
                        )
                    # Merge top-level spec fields for later use
                    merged_spec = spec
                else:
                    # Simple payload: build injection from spec
                    payload = spec.get("payload_content", "") if isinstance(spec, dict) else str(spec)
                    injection_type = self._normalize_injection_type(spec.get("injection_type", "append") if isinstance(spec, dict) else "append")
                    match_pattern = spec.get("match_pattern", "") if isinstance(spec, dict) else ""
                    
                    updated_injections.append(
                        PromptInjection(
                            target_file_path=injection.target_file_path,
                            injection_type=injection_type,
                            match_pattern=match_pattern,
                            payload_content=payload,
                        )
                    )

        # If no base_sample.prompt_injections, generate without injection context
        # AND check that we haven't already populated updated_injections via reuse
        if not self.base_sample.prompt_injections and not (self.reuse_first and attempt_idx == 0 and updated_injections):
            spec = self.generator.generate(
                feedback=feedback,
                attempt_idx=attempt_idx,
                channel=self.channel,
                file_path=self.file_path,
            )
            merged_spec = spec

        # Merge metadata from spec if available
        merged_metadata = dict(self.base_sample.metadata or {})
        if merged_spec.get("thought_process"):
            merged_metadata["thought_process"] = merged_spec.get("thought_process")
        if merged_spec.get("category"):
            merged_metadata.setdefault("category", merged_spec.get("category"))
        if merged_spec.get("subcategory"):
            merged_metadata.setdefault("subcategory", merged_spec.get("subcategory"))

        # Build updated sample
        updated_sample = Sample(
            id=merged_spec.get("id", self.base_sample.id) if merged_spec else self.base_sample.id,
            user_instruction=merged_spec.get("user_instruction") or self.base_sample.user_instruction if merged_spec else self.base_sample.user_instruction,
            target=self.base_sample.target,
            metadata=merged_metadata,
            custom_html_content=merged_spec.get('custom_html_content') or self.base_sample.custom_html_content if merged_spec else self.base_sample.custom_html_content,
            env_setup_script=merged_spec.get("environment_setup") or self.base_sample.env_setup_script if merged_spec else self.base_sample.env_setup_script,
            workspace=self.base_sample.workspace,
            script_to_fetch_from_attacker_server=merged_spec.get('script_to_fetch_from_attacker_server') or self.base_sample.script_to_fetch_from_attacker_server if merged_spec else self.base_sample.script_to_fetch_from_attacker_server,
            prompt_injections=updated_injections,
            evaluation=merged_spec.get("evaluation") or self.base_sample.evaluation if merged_spec else self.base_sample.evaluation,
            category=merged_spec.get("category") or self.base_sample.category if merged_spec else self.base_sample.category,
            subcategory=merged_spec.get("subcategory") or self.base_sample.subcategory if merged_spec else self.base_sample.subcategory,
        )

        try:
            REGISTRY.save_sample(updated_sample)
        except Exception as e:
            # Don't fail the session if saving to registry fails
            print(f"Warning: Failed to save sample {updated_sample.id} to registry: {e}")
        
        return AttackAttempt(sample=updated_sample, metadata=metadata)


class StaticPromptInjectionSession(RegenerativeSessionBase):
    """
    Static regenerative session that uses existing prompt_injections without LLM generation.
    Useful for template-based or pre-crafted attacks.
    """

    def __init__(
        self,
        base_sample: Sample,
        channel: str = "input",
        max_rounds: int = 3,
        file_path: Optional[str] = None,
    ):
        super().__init__(max_rounds=max_rounds)
        self.base_sample = base_sample
        self.channel = channel
        self.file_path = file_path

    def _normalize_injection_type(self, raw: str) -> str:
        if raw == "replace_match":
            return "replace"
        return raw or "append"

    def _build_attempt(self, sample: Optional[Sample], feedback: Optional[AttackFeedback], attempt_idx: int) -> AttackAttempt:
        """
        Build attempt by keeping existing injections unchanged.
        Useful for static/template-based attacks that don't require regeneration.
        """
        metadata = {
            "attempt_idx": attempt_idx,
            "channel": self.channel,
            "method": "static",
        }

        return AttackAttempt(sample=self.base_sample, metadata=metadata)
