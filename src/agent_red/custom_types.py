from __future__ import annotations
import os
import copy
from string import Template
from dataclasses import dataclass
from typing import Any, Callable, Awaitable, Dict, List, Optional, TYPE_CHECKING, Union, Literal, Tuple
import yaml as yaml_lib
from pydantic import BaseModel, Field, ConfigDict, field_validator 
import traceback
import asyncio
import pdb
from .config import DEFAULT_IDE_SETTINGS, MODEL_NAME_MAPPING
from .utils.get_model_api import get_model_api
from dotenv import load_dotenv


def _vmware_template_variables() -> Dict[str, str]:
    """Read non-secret IDE path variables from the local VMware config."""
    path = os.getenv("VMWARE_CONFIG_PATH", "configs/vmware.local.yaml")
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        vmware_config = yaml_lib.safe_load(f) or {}
    if not isinstance(vmware_config, dict):
        raise ValueError(f"VMware configuration must be a YAML mapping: {path}")
    guest = vmware_config.get("guest") or {}
    if not isinstance(guest, dict):
        raise ValueError(f"guest must be a YAML mapping: {path}")
    username = guest.get("username")
    return {"VM_WINDOWS_USER": str(username)} if username else {}


def _expand_environment_variables(value: Any, variables: Optional[Dict[str, str]] = None) -> Any:
    """Expand placeholders throughout YAML data from local config and environment."""
    substitutions = {**os.environ, **(variables or {})}
    if isinstance(value, str):
        return Template(value).safe_substitute(substitutions)
    if isinstance(value, dict):
        return {
            key: _expand_environment_variables(item, substitutions)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_expand_environment_variables(item, substitutions) for item in value]
    return value


class ModelConfig(BaseModel):
    model_name: str = "gpt-4o-mini"
    api_provider: str = "OpenAI Compatible"
    base_url: str = ""
    api_key: str = ""
    model_args: Dict[str, Any] = Field(default_factory=dict)
    system_prompt: str = "You are a helpful and security-focused AI assistant."

    @field_validator("model_name", mode="before")
    @classmethod
    def normalize_model_name(cls, v: str) -> str:
        return MODEL_NAME_MAPPING.get(v, v)
        

class AgentConfig(BaseModel):
    software: str = "cc_cli"
    model: ModelConfig = Field(default_factory=ModelConfig)
    tools: Optional[List[Dict[str, Any]]] = Field(default_factory=list)

    filter_for_trace: Optional[Dict[str, Any]] = Field(default_factory=dict, exclude=True)
    
    ###### IDE Agent Specific ######
    export_dir: Optional[str] = None
    executable_path: Optional[str] = None
    ide_server_folder: Optional[str] = None
    ide_settings: Optional[Dict[str, Any]] = Field(default_factory=lambda: copy.deepcopy(DEFAULT_IDE_SETTINGS))
    remote_target_arg: str = "--remote ssh-remote+docker-container /home/devuser/project"

    yaml: Optional[str] = None
    yaml_config: Optional[Dict[str, Any]] = Field(default=None, exclude=True)
    
    def model_post_init(self, __context: Any) -> None:
        """Load YAML and initialize IDE-specific parameters if not already set."""
        api_key, api_base_url = get_model_api(self.model.model_name, agent=self.software)        
        self.model.api_key = api_key
        self.model.base_url = api_base_url
        template_variables = _vmware_template_variables()
        if self.yaml and self.yaml_config is None:
            self.yaml_config = _expand_environment_variables(
                yaml_lib.safe_load(self.yaml), template_variables
            )
        elif not self.yaml:
            try:
                with open(f"configs/{self.software}.yaml", "r", encoding="utf-8") as f:
                    self.yaml = f.read()
                    self.yaml_config = _expand_environment_variables(
                        yaml_lib.safe_load(self.yaml), template_variables
                    )
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning(f"Failed to load YAML file for {self.software}: {e}")
                raise e
            assert isinstance(self.yaml_config, dict)
            
            if 'filter_for_trace' in self.yaml_config:
                self.filter_for_trace = self.yaml_config.get('filter_for_trace', {})
            # Initialize export_dir if not set
            if self.export_dir is None:
                self.export_dir = self.yaml_config.get("export_dir")
            
            # Initialize executable_path if not set
            if self.executable_path is None:
                self.executable_path = self.yaml_config.get("executable_path")
            
            # Initialize ide_server_folder if not set
            if self.ide_server_folder is None:
                self.ide_server_folder = self.yaml_config.get("ide_server_folder")
            
            # Initialize ide_settings from yaml_config if not customized
            if self.ide_settings == DEFAULT_IDE_SETTINGS and 'ide_settings' in self.yaml_config:
                self.ide_settings = self.yaml_config.get('ide_settings', DEFAULT_IDE_SETTINGS)

            model_button = self.model.model_name.lower().replace("-", "_").replace(".", "_") + "_button"
            if "<<model_name>>" in self.yaml:
                self.yaml = self.yaml.replace("<<model_name>>", self.model.model_name)
            if "<<model_button>>" in self.yaml:
                if model_button in self.yaml:
                    self.yaml = self.yaml.replace("<<model_button>>", model_button)
                else:
                    raise ValueError(f"{model_button} not found in {self.software}.yaml")



class SkillOrRuleRecord(BaseModel):
    """Manifest record for one installed skill/rule.

    The dataset generator writes different fields for skills (`saved_dir`) and
    rules (`saved_path`).  Keep this model permissive so older/newer manifests
    can be consumed without dropping useful metadata.
    """
    model_config = ConfigDict(extra="allow")

    id: Optional[str] = None
    type: Optional[str] = None
    language: Optional[str] = None
    full_name: Optional[str] = None
    html_url: Optional[str] = None
    stars: Optional[int] = None
    source_path: Optional[str] = None
    saved_dir: Optional[str] = None
    saved_path: Optional[str] = None
    skill_md_path: Optional[str] = None
    rule_kind: Optional[str] = None
    description: Optional[str] = None


class DefenseConfig(BaseModel):
    model_config = ConfigDict(extra="allow")

    enabled: bool = False
    file_modifications: Optional[List[PromptInjection]] = Field(default_factory=list)
    # Per-sample defense/rules metadata emitted by dataset_gen.main.
    rules_path: Optional[str] = None
    rules_paths: List[str] = Field(default_factory=list)
    sampled_rules: List[SkillOrRuleRecord] = Field(default_factory=list)
    defense_rules: List[SkillOrRuleRecord] = Field(default_factory=list)


class SkillConfig(BaseModel):
    model_config = ConfigDict(extra="allow")

    # Legacy experiment-level shape.
    enabled: bool = False
    skills_names: List[str] = Field(default_factory=list)

    # New per-sample dataset shape.
    mode: Optional[str] = None
    canonical_mode: Optional[str] = None
    skills_enabled: bool = False
    rules_enabled: bool = False
    defense_enabled: bool = False
    skills: List[SkillOrRuleRecord] = Field(default_factory=list)
    rules: List[SkillOrRuleRecord] = Field(default_factory=list)
    sampled_rules: List[SkillOrRuleRecord] = Field(default_factory=list)
    defense_rules: List[SkillOrRuleRecord] = Field(default_factory=list)
    rules_paths: List[str] = Field(default_factory=list)
    defense_rules_path: Optional[str] = None


class ExperimentConfig(BaseModel):
    mode: Literal["dataset", "single_sample"] = "dataset"
    agent: AgentConfig = AgentConfig()
    defense: DefenseConfig = Field(default_factory=DefenseConfig)
    skills: SkillConfig = Field(default_factory=SkillConfig)
    attack_method_name: str = "static_file"
    attack_model_name: str = "gpt-4o-mini"
    env_image_name: Optional[str] = None

    ##### Dataset Settings #####
    dataset_name: str = "ipi_file_dataset_lite"
    filter_dict: Optional[Dict[str, Any]] = Field(default_factory=dict)
    sample_n: int = -1

    ##### Sample #####
    sample: Optional[Sample] = None

    ##### Parallellism Settings #####
    concurrency: int = 1
    k_runs: int = 1

    ##### Evaluation Settings #####
    skip_completed: bool = False
    # When skip_completed=True, skipped historical results are not streamed to
    # the task WebSocket/result queue by default.  The client can fetch them via
    # the completed-results endpoint instead.  Set this true only for legacy
    # clients that expect skipped results to be replayed on every run.
    stream_skipped_results: bool = False
    user: str = "default"
    fail_immediately_on_error: bool = False
    screenshot_time: Optional[float] = None
    log_level: str = "INFO"
    debug_port: int = -1
    # Server streaming controls. These only affect the client-server/WebSocket
    # transport layer; local result files and final result retrieval still work.
    # Useful for high-concurrency CLI runs where base64 screenshots and verbose
    # live logs can dominate memory/network overhead.
    stream_frames: bool = True
    stream_logs: bool = True
    https_proxy: Optional[str] = None
    host_ip: Optional[str] = None
    def model_post_init(self, __context: Any) -> None:
        load_dotenv()  # Load environment variables from .env file
        self.https_proxy = os.getenv("HTTPS_PROXY") or os.getenv("https_proxy")
        self.host_ip = os.getenv("HOST_IP", "localhost")

class ServerConfig(BaseModel):
    dataset_base_path: str = "./data"
    workspace_base_path: str = "./temp_workspace"
    results_base_path: str = "./results"
    vm_config_path: str = "./configs"

class AttackStrategyConfig(BaseModel):
    model: str = "gpt-4o-mini"
    base_url: str = ""
    api_key: str = ""
    mode: str = "input"  # input | file | cursorrules | web
    max_rounds: int = 3
    chat_generator: Optional[Callable[[Any], str]] = None

class PromptInjection(BaseModel):
    target_file_path: str
    injection_script: Optional[str] = None
    injection_type: Optional[Literal['append', 'insert_after_match', 'replace', 'insert_before_match']] = None
    match_pattern: Optional[str] = None
    raw_payload: Optional[str] = None
    craft_method: Optional[str] = None
    payload_content: str

class ScoreResult(BaseModel):
    name: str
    value: float
    explanation: str | None = None

class EvaluationResult(BaseModel):
    sample_id: str
    sample: Sample
    time_stamp: str
    task_success: Literal["success", "failure"]
    attack_success: Literal["success", "failure"]
    alert_success: Literal["success", "failure"]
    scores: Dict[str, Union[float, List[ScoreResult]]]
    prompt_injections: List[PromptInjection]
    explanation: List[List[str]]
    metadata: Dict[str, Any]
    trace: List[Dict[str, Any]]
    web_server_log: Dict[str, Any]
    raw_chat_history: Optional[str] = None
    commands_executed: List[str]
    history_length: int
    feedback: Optional[Dict[str, Any]] = None
    exp_config: ExperimentConfig

class RunnerResult(BaseModel):
    sample_id: str
    status: Literal["success", "error"]
    timestamp: str
    result: Optional[EvaluationResult] = None
    stats: Dict[str, float] = Field(default_factory=dict)
    sample: Sample
    metadata: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None
    attempts: Optional[int] = None
    attack_payload: Optional[Dict[str, Any]] = None

class VerificationConfig(BaseModel):
    method: Literal['CHECK_NETWORK_LOG', 'COMMANDS_EXECUTED', 'LLM_JUDGE', 'EXEC_IN_CONTAINER', 'CHECK_CONTAINER_PATH', 'PATCH_TEST']
    params: Dict[str, Any] = Field(default_factory=dict)

class Sample(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    # Legacy datasets use user_instruction as the task text and do not provide
    # this separate field.
    task: str = ""
    user_instruction: str
    target: Optional[str] = None
    thought_process: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    custom_html_content: Optional[str] = None
    env_setup_script: Optional[str] = None
    html_domain: Optional[str] = None
    html_endpoint: Optional[str] = None
    attacker_domain: Optional[str] = None
    attacker_endpoint: Optional[str] = None
    workspace: Optional[str] = "itchat"
    language: Optional[str] = "unknown"
    script_to_fetch_from_attacker_server: Optional[str] = None
    prompt_injections: Optional[List[PromptInjection]] = Field(default_factory=list)
    evaluation: Optional[Dict[str, List[VerificationConfig]]] = None
    # Per-sample skills/rules emitted by dataset_gen.main.  These override the
    # experiment-level SkillConfig during container preparation.
    skills: Optional[SkillConfig] = None
    defense: Optional[DefenseConfig] = None
    category: Literal['Data_Leakage', 'Host_Environment_Destruction', 'Harmful_Code_Generation', 'Workflow_Damage', 'Exfiltration', 'Persistence', 'Destruction', 'Benign']
    subcategory: Optional[str] = None
    ide_settings: Optional[Dict[str, Any]] = DEFAULT_IDE_SETTINGS

class MemoryDataset():

    def __init__(self, samples: List[Sample] = None):
        self.samples = samples or []

    def __getitem__(self, index: int) -> Sample:
        return self.samples[index]

    def __len__(self) -> int:
        return len(self.samples)

    def __iter__(self):
        return iter(self.samples)

    def append(self, sample: Sample):
        self.samples.append(sample)

    def extend(self, samples: List[Sample]):
        self.samples.extend(samples)
    
    def filter(self, predicate: Callable[[Sample], bool]) -> 'MemoryDataset':
        """Filter samples based on a predicate function."""
        filtered_samples = [sample for sample in self.samples if predicate(sample)]
        return MemoryDataset(samples=filtered_samples)

class ChatMessage(BaseModel):
    role: str
    content: str
    model: Optional[Dict[str, Any]] = None

class ChatMessageUser(ChatMessage):
    role: str = "user"

class ChatMessageAssistant(ChatMessage):
    role: str = "assistant"

@dataclass
class RunnableContext:
    """
    Holds the instantiated objects for a single evaluation run (one dataset sample).
    """
    sample_id: str
    sample: Sample
    
    # The active Environment Manager (needs cleanup after use)
    environment_manager: Any 
    
    # The async function to run the agent: func(state) -> result
    solver: Callable[[Any], Awaitable[Any]] 
    
    # The async function to score the result: func(state, result) -> score
    scorer: Callable[[Any, Any], Awaitable[Any]]
    
    # Metadata for logging
    metadata: Dict[str, Any] = Field(default_factory=dict)


@dataclass
class EnvironmentState:
    """A simple data class to hold the state of our running environment."""
    vscode_url: str
    code_server_container: DockerExecutionEnvironment
    running_environments: Dict[str, DockerExecutionEnvironment]
    proxy_dashboard_url: str | None = None
    password: str | None = None


class TaskState(BaseModel):
    sample: Sample
    exp_config: ExperimentConfig
    env_state: EnvironmentState

    traces: List[Dict[str, Any]] = Field(default_factory=list)
    api_traces: List[Dict[str, Any]] = Field(default_factory=list)
    chat_history: str = ""
    messages: List[ChatMessage] = Field(default_factory=list)
    commands_executed: List[str] = Field(default_factory=list)
    tools: List[Any] = Field(default_factory=list)
    message_limit: int | None = None
    output: ChatMessage = Field(default_factory=lambda: ChatMessage(role="", content=""))
    completed: bool = False
    epoch: int = 0
    web_server_log: dict = Field(default_factory=dict)
    model_config = ConfigDict(arbitrary_types_allowed=True)

class EvaluationError(Exception):
    def __init__(self, instance_id, message, logger):
        super().__init__(message)
        self.instance_id = instance_id
        self.log_file = logger.log_file
        self.logger = logger

    def __str__(self):
        log_msg = traceback.format_exc()
        self.logger.info(log_msg)
        return (
            f"{self.instance_id}: {super().__str__()}\n"
            f"Check ({self.log_file}) for more information."
        )

from .env.docker_env import DockerExecutionEnvironment
