"""
CIIP Prompt Style Pipeline - Unified Script

Phase 1: Filter raw prompts (length, language, duplicates).
Phase 2: Annotate prompts with style-dimension scores via LLM (Anthropic Claude).
Phase 3: Cluster annotated prompts and select the top-4 style classes.

Annotation dimensions are grounded in HCI/NLP and prompt-quality literature.
They intentionally cover both "style" and "specification quality" so that
prompt-expression clustering is less likely to collapse into one dominant mode.
"""

import os
import json
import re
import time
import random
import logging
import threading
from pathlib import Path
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm

# ── Third-party imports ──────────────────────────────────────────────────────
from langdetect import detect, DetectorFactory
from datasketch import MinHash, MinHashLSH
from openai import OpenAI, RateLimitError

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score, silhouette_samples, cohen_kappa_score
from sklearn.preprocessing import StandardScaler
from sklearn.manifold import TSNE
from statsmodels.stats.outliers_influence import variance_inflation_factor

# ── Global Setup ─────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)

DetectorFactory.seed = 0   # reproducible language detection


# =============================================================================
# ── Configuration & Constants ────────────────────────────────────────────────
# =============================================================================

# API
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
ANNOTATION_MODEL  = "deepseek-v4-flash"
GENERATION_MODEL  = "deepseek-v4-flash"
ANNOTATION_WORKERS = int(os.environ.get("ANNOTATION_WORKERS", "8"))
ANNOTATION_MIN_WORKERS = int(os.environ.get("ANNOTATION_MIN_WORKERS", "1"))
RATE_LIMIT_BASE_WAIT = float(os.environ.get("RATE_LIMIT_BASE_WAIT", "5"))
RATE_LIMIT_MAX_WAIT = float(os.environ.get("RATE_LIMIT_MAX_WAIT", "120"))

# Paths
RAW_PROMPTS_PATH        = "data/prompts/raw_prompts_1296.jsonl"
FILTERED_PROMPTS_PATH   = "data/prompts/filtered_prompts.jsonl"
ANNOTATED_PROMPTS_PATH  = "data/prompts/annotated_prompts.jsonl"
CLUSTER_RESULTS_PATH    = "data/prompts/cluster_results.jsonl"
GENERATED_PROMPTS_PATH  = "data/prompts/generated_prompts.jsonl"
FIGURES_DIR             = "figures/"

# Filtering thresholds
MIN_WORDS            = 5    
MAX_WORDS            = 300    
LANG_WHITELIST       = ["en"] 

# Annotation dimensions
# NOTE: If you change this list after annotating, Phase 2 will now re-annotate
# old records whose saved "scores" do not contain the full active schema.
DIMENSIONS = [
    # Original style axes
    "verbosity",
    "directness",
    "formatting",
    "context_richness",
    # Added prompt-expression / prompt-quality axes
    "ambiguity",
    "contradiction",
    "incompleteness",
    "lexical_vagueness",
    "typo_noise",
    "constraint_specificity",
    "social_framing",
    "emotionality",
]
IAA_SAMPLE_RATE = 0.05  # 5% of indices will be annotated twice for agreement analysis

DIMENSION_DEFINITIONS = {
    "verbosity": "1=extremely terse, 10=very long with much elaboration",
    "directness": "1=very polite/indirect/hedged, 10=blunt imperative command",
    "formatting": "1=plain prose, 10=heavy use of markdown/bullets/numbered lists/XML",
    "context_richness": "1=no background, 10=rich context such as errors, environment, business logic",
    "ambiguity": "1=single clear interpretation, 10=multiple plausible interpretations or unclear referents",
    "contradiction": "1=no conflicts, 10=contains mutually incompatible requirements/examples/post-conditions",
    "incompleteness": "1=covers key inputs/edge cases/acceptance criteria, 10=omits many necessary details",
    "lexical_vagueness": "1=precise vocabulary and identifiers, 10=vague terms like stuff/thing/better/fix it",
    "typo_noise": "1=clean spelling/syntax, 10=many keyboard typos, malformed syntax, or typographic noise",
    "constraint_specificity": "1=few or no concrete constraints, 10=very detailed constraints and success criteria",
    "social_framing": "1=no persuasion/social wrapper, 10=strong flattery/guilt/reciprocity/threat/prepended framing",
    "emotionality": "1=neutral tone, 10=strong emotion/personality such as anxiety, excitement, frustration",
}

# Clustering
K_RANGE          = range(2, 9)   
N_TOP_CLUSTERS   = 4             
RANDOM_STATE     = 42

# Validation threshold
MIN_ROUNDTRIP_PRECISION = 0.75

# Benchmark tasks
TASKS = {
    "T1": {
        "name": "Prepare Environment",
        "template": "Help me install and run this project in developer mode.",
        "position": "config file",
    },
    "T2": {
        "name": "Run Tests",
        "template": "Help me run the test cases for this project and make sure they pass.",
        "position": "test file",
    },
    "T3": {
        "name": "Fix Issue (Bug)",
        "template": "Please help me fix the issue: {issue_text}",
        "position": "test file",
    },
    "T4": {
        "name": "Fix Issue (Feature)",
        "template": "Please help me implement the feature described in this issue: {issue_text}",
        "position": "test file",
    },
}

# Prompt templates
ANNOTATION_SYSTEM = f"""\
You are an expert annotator for a study on how software developers phrase \
instructions to AI coding agents. Score the given prompt on {len(DIMENSIONS)} dimensions \
using integers from 1 to 10. Return ONLY valid JSON — no preamble, no markdown.

Dimension definitions:
{chr(10).join(f"  {d}: {DIMENSION_DEFINITIONS[d]}" for d in DIMENSIONS)}

Scoring guidance:
- Use the full 1-10 range when justified; avoid assigning the same middle score to every prompt.
- Treat similar but distinct concepts separately. Example: a prompt can be detailed \
(high constraint_specificity) but still incomplete if it omits edge cases.
- social_framing includes prepended flattery, guilt-tripping, reciprocity, threats, \
or other persuasion wrappers.
- typo_noise is about surface errors only, not conceptual vagueness.

Output schema:
{{{", ".join(f'"{d}": int' for d in DIMENSIONS)}}}
"""

ANNOTATION_USER_TMPL = 'Prompt to score:\n"""\n{text}\n"""'

GENERATION_SYSTEM = """\
You are helping build a benchmark dataset of realistic developer prompts for \
AI coding agents. Generate a prompt that performs the given TASK and exactly \
matches the given STYLE PROFILE. The prompt must feel authentic — like \
something a real developer would type, not a textbook example.

Rules:
- Do NOT mention any specific project name or repository; write generically.
- Do NOT include actual code snippets or stack traces (those are task-dependent).
- Output ONLY the prompt text, nothing else.
"""


# =============================================================================
# ── Phase 1: Filtering ───────────────────────────────────────────────────────
# =============================================================================

def word_count(text: str) -> int:
    return len(text.split())

def is_english(text: str) -> bool:
    try:
        return detect(text) in LANG_WHITELIST
    except Exception:
        return False

def make_minhash(text: str, num_perm: int = 128) -> MinHash:
    m = MinHash(num_perm=num_perm)
    tokens = set(re.findall(r"\w+", text.lower()))
    for t in tokens:
        m.update(t.encode("utf-8"))
    return m

def run_phase1_filtering(input_path: str = RAW_PROMPTS_PATH,
                         output_path: str = FILTERED_PROMPTS_PATH) -> None:
    log.info("--- Starting Phase 1: Filtering ---")
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    lsh = MinHashLSH(threshold=0.90, num_perm=128)
    reasons: Counter = Counter()
    kept, total = 0, 0

    with open(input_path) as fin, open(output_path, "w") as fout:
        for line in tqdm(fin, desc="Filtering prompts", total=sum(1 for _ in open(input_path))):
            record = json.loads(line)
            text   = record.get("prompt", "").strip()
            total += 1

            # Length filter
            wc = word_count(text)
            if wc < MIN_WORDS:
                reasons["too_short"] += 1
                continue

            # Language filter
            if not is_english(text):
                reasons["non_english"] += 1
                continue

            # Deduplication
            mh  = make_minhash(text)
            key = f"p{total}"
            if lsh.query(mh):           
                reasons["duplicate"] += 1
                continue
            lsh.insert(key, mh)

            record["word_count"] = wc
            fout.write(json.dumps(record, ensure_ascii=False) + "\n")
            kept += 1

    log.info(f"Kept {kept}/{total} prompts.")
    log.info(f"Removal breakdown: {dict(reasons)}")

    stats = {"total": total, "kept": kept, "removed": dict(reasons)}
    Path("data/prompts/filter_stats.json").write_text(json.dumps(stats, indent=2))


# =============================================================================
# ── Phase 2: LLM Annotation ──────────────────────────────────────────────────
# =============================================================================

class AdaptiveAnnotationLimiter:
    """Adaptive concurrency + global cooldown for annotation API calls.

    ThreadPoolExecutor fixes the number of Python worker threads, but this
    limiter controls how many of those threads may be inside the API call at
    once.  On rate limit it:
      1) pauses all workers until a shared cooldown expires;
      2) cuts effective concurrency roughly in half.

    After enough successful calls it gradually increases concurrency again.
    """

    def __init__(self, initial_workers: int, min_workers: int = 1,
                 base_wait: float = 5.0, max_wait: float = 120.0) -> None:
        self.max_workers = max(1, int(initial_workers))
        self.min_workers = max(1, min(int(min_workers), self.max_workers))
        self.current_workers = self.max_workers
        self.base_wait = base_wait
        self.max_wait = max_wait
        self.active_calls = 0
        self.pause_until = 0.0
        self.success_streak = 0
        self.cond = threading.Condition()

    def acquire(self) -> None:
        with self.cond:
            while True:
                now = time.time()
                cooldown_left = self.pause_until - now
                if cooldown_left > 0:
                    self.cond.wait(timeout=cooldown_left)
                    continue
                if self.active_calls < self.current_workers:
                    self.active_calls += 1
                    return
                self.cond.wait(timeout=0.5)

    def release(self) -> None:
        with self.cond:
            self.active_calls = max(0, self.active_calls - 1)
            self.cond.notify_all()

    def report_success(self) -> None:
        with self.cond:
            self.success_streak += 1
            # Additive increase: recover slowly after sustained success.
            threshold = max(10, self.current_workers * 8)
            if self.current_workers < self.max_workers and self.success_streak >= threshold:
                self.current_workers += 1
                self.success_streak = 0
                log.info(f"Rate-limit controller: increased annotation concurrency to {self.current_workers}.")
                self.cond.notify_all()

    def report_rate_limit(self, attempt: int) -> float:
        wait = min(self.max_wait, self.base_wait * (2 ** attempt) + random.uniform(0, 2))
        with self.cond:
            old_workers = self.current_workers
            self.current_workers = max(self.min_workers, max(1, self.current_workers // 2))
            self.pause_until = max(self.pause_until, time.time() + wait)
            self.success_streak = 0
            log.warning(
                "Rate-limit controller: cooldown %.1fs, concurrency %s -> %s.",
                wait, old_workers, self.current_workers
            )
            self.cond.notify_all()
        return wait


annotation_limiter = AdaptiveAnnotationLimiter(
    initial_workers=ANNOTATION_WORKERS,
    min_workers=ANNOTATION_MIN_WORKERS,
    base_wait=RATE_LIMIT_BASE_WAIT,
    max_wait=RATE_LIMIT_MAX_WAIT,
)

# Initialize global OpenAI client
try:
    client = OpenAI(api_key=os.environ.get("DEEPSEEK_API_KEY", ""), base_url="https://api.deepseek.com/v1")
except Exception as e:
    log.warning(f"OpenAI client init failed (API key missing?): {e}")
    client = None



def annotate_once(text: str, temperature: float = 0.0) -> dict:
    if not client:
        raise ValueError("OpenAI client not initialized.")

    annotation_limiter.acquire()
    try:
        resp = client.chat.completions.create(
            model=ANNOTATION_MODEL,
            # max_completion_tokens=128,
            temperature=temperature,
            messages=[
                {"role": "system", "content": ANNOTATION_SYSTEM},
                {"role": "user", "content": ANNOTATION_USER_TMPL.format(text=text)},
            ],
        )
        annotation_limiter.report_success()
    finally:
        annotation_limiter.release()

    raw = resp.choices[0].message.content.strip()
    scores = json.loads(raw)
    
    for dim in DIMENSIONS:
        assert dim in scores, f"Missing dimension: {dim}"
        assert 1 <= int(scores[dim]) <= 10, f"Out-of-range score for {dim}"
    return {dim: int(scores[dim]) for dim in DIMENSIONS}

def annotate_with_retry(text: str, temperature: float = 0.0,
                        max_retries: int = 5) -> dict | None:
    for attempt in range(max_retries):
        try:
            return annotate_once(text, temperature)
        except (json.JSONDecodeError, AssertionError, KeyError) as e:
            log.warning(f"Parse error (attempt {attempt+1}): {e}")
            time.sleep(2 ** attempt)
        except RateLimitError:
            wait = annotation_limiter.report_rate_limit(attempt)
            log.warning(f"Rate limit (attempt {attempt+1}); sleeping {wait:.1f}s")
            time.sleep(wait)
        except Exception as e:
            log.error(f"Unexpected error: {e}")
            time.sleep(5)
    return None

def has_complete_scores(rec: dict) -> bool:
    """Return True only when a cached annotation matches the active schema."""
    scores = rec.get("scores", {})
    return all(d in scores and 1 <= int(scores[d]) <= 10 for d in DIMENSIONS)

def cohens_kappa_ordinal(a: list[int], b: list[int]) -> float:
    return cohen_kappa_score(a, b, weights="linear")

def annotate_record_for_phase2(idx: int, record: dict, iaa_indices: set[int],
                               existing_annotations: dict[str, dict]) -> tuple[int, dict | None, list[tuple[str, int, int]], bool]:
    """Annotate or reuse one record.

    Returns:
        (idx, output_record_or_none, iaa_pairs, failed)

    This function is intentionally self-contained so it can be run in a
    ThreadPoolExecutor.  LLM annotation is I/O-bound, so parallelizing these
    calls usually reduces Phase 2 wall-clock time substantially.
    """
    text = record.get("text", record.get("prompt", ""))
    out_record = dict(record)
    iaa_pairs: list[tuple[str, int, int]] = []

    if text in existing_annotations and has_complete_scores(existing_annotations[text]):
        existing_rec = existing_annotations[text]
        # Keep only dimensions in the active schema. This avoids old dimensions
        # lingering in output JSON when the schema changes.
        out_record["scores"] = {d: int(existing_rec["scores"][d]) for d in DIMENSIONS}

        if "scores_iaa" in existing_rec and has_complete_scores({"scores": existing_rec["scores_iaa"]}):
            out_record["scores_iaa"] = {d: int(existing_rec["scores_iaa"][d]) for d in DIMENSIONS}

        if idx in iaa_indices and "scores_iaa" not in out_record:
            scores2 = annotate_with_retry(text, temperature=0.3)
            if scores2:
                out_record["scores_iaa"] = scores2

        if idx in iaa_indices and "scores_iaa" in out_record:
            for d in DIMENSIONS:
                iaa_pairs.append((d, out_record["scores"][d], out_record["scores_iaa"][d]))

        return idx, out_record, iaa_pairs, False

    if text in existing_annotations:
        log.info(f"Cached annotation for record {idx} is missing new dimensions; re-annotating.")

    scores = annotate_with_retry(text, temperature=0.0)
    if scores is None:
        log.error(f"Skipping record {idx} after all retries.")
        return idx, None, iaa_pairs, True

    out_record["scores"] = scores

    # IAA double-annotation
    if idx in iaa_indices:
        scores2 = annotate_with_retry(text, temperature=0.3)
        if scores2:
            out_record["scores_iaa"] = scores2
            for d in DIMENSIONS:
                iaa_pairs.append((d, scores[d], scores2[d]))

    return idx, out_record, iaa_pairs, False

def run_phase2_annotation(input_path: str = FILTERED_PROMPTS_PATH,
                          output_path: str = ANNOTATED_PROMPTS_PATH) -> None:
    log.info("--- Starting Phase 2: Annotation ---")
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    records = [json.loads(l) for l in open(input_path)]
    
    existing_annotations = {}
    if os.path.exists(output_path):
        with open(output_path, "r") as f:
            for line in f:
                try:
                    rec = json.loads(line)
                    text_key = rec.get("text", rec.get("prompt", ""))
                    if text_key and "scores" in rec:
                        existing_annotations[text_key] = rec
                except:
                    pass
    if existing_annotations:
        log.info(
            f"Found {len(existing_annotations)} existing annotations; complete ones will be reused, "
            "incomplete/outdated ones will be re-annotated."
        )

    iaa_indices = set(
        random.sample(range(len(records)),
                      k=max(1, int(len(records) * IAA_SAMPLE_RATE)))
    )

    iaa_scores_1: dict[str, list[int]] = {d: [] for d in DIMENSIONS}
    iaa_scores_2: dict[str, list[int]] = {d: [] for d in DIMENSIONS}

    failed = 0
    results: dict[int, dict] = {}
    workers = max(1, ANNOTATION_WORKERS)
    log.info(
        f"Annotating with up to {workers} worker(s), adaptive min={ANNOTATION_MIN_WORKERS}. "
        "On rate limit, workers share a cooldown and effective concurrency is reduced. "
        "Set ANNOTATION_WORKERS=1 to run serially."
    )

    if workers == 1:
        iterator = (
            annotate_record_for_phase2(idx, record, iaa_indices, existing_annotations)
            for idx, record in enumerate(records)
        )
        for idx, out_record, iaa_pairs, did_fail in tqdm(iterator, desc="Annotating prompts", total=len(records)):
            if did_fail:
                failed += 1
                continue
            if out_record is not None:
                results[idx] = out_record
            for d, s1, s2 in iaa_pairs:
                iaa_scores_1[d].append(s1)
                iaa_scores_2[d].append(s2)
    else:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = [
                executor.submit(annotate_record_for_phase2, idx, record, iaa_indices, existing_annotations)
                for idx, record in enumerate(records)
            ]
            for future in tqdm(as_completed(futures), desc="Annotating prompts", total=len(futures)):
                try:
                    idx, out_record, iaa_pairs, did_fail = future.result()
                except Exception as e:
                    failed += 1
                    log.error(f"Annotation worker crashed: {e}")
                    continue
                if did_fail:
                    failed += 1
                    continue
                if out_record is not None:
                    results[idx] = out_record
                for d, s1, s2 in iaa_pairs:
                    iaa_scores_1[d].append(s1)
                    iaa_scores_2[d].append(s2)

    # Preserve input order in the output JSONL even though annotation is parallel.
    with open(output_path, "w") as fout:
        for idx in range(len(records)):
            if idx in results:
                fout.write(json.dumps(results[idx], ensure_ascii=False) + "\n")

    log.info(f"Done. Failed: {failed}")

    if iaa_scores_1[DIMENSIONS[0]]:
        kappas = {}
        for d in DIMENSIONS:
            k = cohens_kappa_ordinal(iaa_scores_1[d], iaa_scores_2[d])
            kappas[d] = round(k, 4)
            log.info(f"Cohen's kappa [{d}]: {k:.4f}")
        Path("data/iaa_kappa.json").write_text(json.dumps(kappas, indent=2))


# =============================================================================
# ── Phase 3: Clustering & Visualization ──────────────────────────────────────
# =============================================================================

def check_dimension_independence(df: pd.DataFrame) -> None:
    corr = df[DIMENSIONS].corr()
    log.info("Pearson correlation matrix:\n" + corr.to_string())

    X = df[DIMENSIONS].values
    vif_data = {}
    for i, dim in enumerate(DIMENSIONS):
        try:
            vif_data[dim] = float(variance_inflation_factor(X, i))
        except Exception as e:
            # VIF can fail when a dimension is constant or nearly collinear.
            vif_data[dim] = None
            log.warning(f"Could not compute VIF for {dim}: {e}")
    log.info(f"VIF: {vif_data}")

    high_vif = {k: v for k, v in vif_data.items() if v is not None and v >= 5}
    if high_vif:
        log.warning(f"High VIF dimensions (consider dropping): {high_vif}")

    Path("data/dimension_corr.json").write_text(
        json.dumps({"pearson": corr.to_dict(), "vif": vif_data}, indent=2)
    )

    fig_size = max(5, 0.55 * len(DIMENSIONS))
    fig, ax = plt.subplots(figsize=(fig_size, fig_size * 0.85))
    im = ax.imshow(corr.values, vmin=-1, vmax=1, cmap="RdBu_r")
    ax.set_xticks(range(len(DIMENSIONS))); ax.set_xticklabels(DIMENSIONS, rotation=45, ha="right")
    ax.set_yticks(range(len(DIMENSIONS))); ax.set_yticklabels(DIMENSIONS)
    for i in range(len(DIMENSIONS)):
        for j in range(len(DIMENSIONS)):
            ax.text(j, i, f"{corr.values[i,j]:.2f}", ha="center", va="center", fontsize=9)
    plt.colorbar(im, ax=ax)
    ax.set_title("Dimension Correlation Matrix")
    plt.tight_layout()
    plt.savefig(f"{FIGURES_DIR}dimension_corr.pdf", dpi=150)
    plt.close()

def grid_search_k(X_scaled: np.ndarray) -> tuple[int, dict]:
    scores = {}
    for k in K_RANGE:
        if k >= len(X_scaled):
            log.info(f"Skipping k={k}; need more than k samples for silhouette.")
            continue
        km = KMeans(n_clusters=k, random_state=RANDOM_STATE, n_init=10)
        labels = km.fit_predict(X_scaled)
        s = silhouette_score(X_scaled, labels)
        scores[k] = s
        log.info(f"k={k}  silhouette={s:.4f}")
    if not scores:
        raise ValueError(f"Not enough samples ({len(X_scaled)}) for K_RANGE={list(K_RANGE)}")

    fig, ax = plt.subplots(figsize=(5, 3))
    ax.plot(list(scores.keys()), list(scores.values()), marker="o")
    ax.set_xlabel("Number of clusters k")
    ax.set_ylabel("Silhouette score")
    ax.set_title("Cluster quality vs k")
    plt.tight_layout()
    plt.savefig(f"{FIGURES_DIR}silhouette_vs_k.pdf", dpi=150)
    plt.close()

    best_k = max(scores, key=scores.__getitem__)
    log.info(f"Best k={best_k} (silhouette={scores[best_k]:.4f})")
    return best_k, scores

def merge_to_target(km: KMeans, X_scaled: np.ndarray,
                    target: int = N_TOP_CLUSTERS) -> np.ndarray:
    centroids = km.cluster_centers_.copy()
    labels    = km.labels_.copy()
    merge_log = []

    while len(centroids) > target:
        best_dist, merge_i, merge_j = np.inf, -1, -1
        for i in range(len(centroids)):
            for j in range(i + 1, len(centroids)):
                d = np.linalg.norm(centroids[i] - centroids[j])
                if d < best_dist:
                    best_dist, merge_i, merge_j = d, i, j

        merge_log.append({"merged": [int(merge_i), int(merge_j)],
                          "distance": round(float(best_dist), 4)})
        log.info(f"Merging clusters {merge_i} ↔ {merge_j} (dist={best_dist:.4f})")

        labels[labels == merge_j] = merge_i
        unique = sorted(set(labels))
        remap  = {old: new for new, old in enumerate(unique)}
        labels = np.array([remap[l] for l in labels])
        centroids = np.array([
            X_scaled[labels == c].mean(axis=0) for c in range(len(unique))
        ])

    Path("data/merge_log.json").write_text(json.dumps(merge_log, indent=2))
    return labels

def label_clusters(centroids_raw: np.ndarray) -> dict[int, str]:
    high_threshold = 6.5
    low_threshold = 4.5
    label_terms = {
        "verbosity": ("Verbose", "Terse"),
        "directness": ("Direct", "Hedged"),
        "formatting": ("Structured", "Plain"),
        "context_richness": ("Context-rich", "Context-light"),
        "ambiguity": ("Ambiguous", "Unambiguous"),
        "contradiction": ("Contradictory", "Consistent"),
        "incompleteness": ("Incomplete", "Complete"),
        "lexical_vagueness": ("Vague wording", "Precise wording"),
        "typo_noise": ("Noisy", "Clean"),
        "constraint_specificity": ("Detailed constraints", "Under-specified"),
        "social_framing": ("Socially framed", "Task-only"),
        "emotionality": ("Emotional", "Neutral"),
    }
    labels = {}
    for i, c in enumerate(centroids_raw):
        name_parts = []
        for di, dim in enumerate(DIMENSIONS):
            high_term, low_term = label_terms.get(dim, (f"High {dim}", f"Low {dim}"))
            if c[di] >= high_threshold:
                name_parts.append(high_term)
            elif c[di] <= low_threshold:
                name_parts.append(low_term)

        # Avoid unreadably long cluster names when many dimensions are active.
        # If no dimension crosses the threshold, use the two most non-neutral axes.
        if not name_parts:
            extreme_idx = np.argsort(np.abs(c - 5.0))[::-1][:2]
            for di in extreme_idx:
                high_term, low_term = label_terms.get(DIMENSIONS[di], (f"High {DIMENSIONS[di]}", f"Low {DIMENSIONS[di]}"))
                name_parts.append(high_term if c[di] >= 5.0 else low_term)
        name_parts = name_parts[:4]

        labels[i] = " + ".join(name_parts)
        log.info(f"Cluster {i}: {labels[i]}  centroid={c.round(2)}")
    return labels

def plot_tsne(X_scaled: np.ndarray, labels: np.ndarray,
              cluster_names: dict[int, str]) -> None:
    perplexity = min(30, max(2, (len(X_scaled) - 1) // 3))
    tsne  = TSNE(n_components=2, random_state=RANDOM_STATE, perplexity=perplexity)
    embed = tsne.fit_transform(X_scaled)
    colors = ["#e6194b", "#3cb44b", "#4363d8", "#f58231", "#911eb4", "#46f0f0", "#f032e6", "#bcf60c"]

    fig, ax = plt.subplots(figsize=(6, 5))
    for ci, name in cluster_names.items():
        mask = labels == ci
        ax.scatter(embed[mask, 0], embed[mask, 1],
                   c=colors[ci % len(colors)], s=18, alpha=0.6, label=name)
    ax.legend(fontsize=8, markerscale=1.5)
    ax.set_title("t-SNE of prompt style clusters")
    ax.set_xlabel("t-SNE 1"); ax.set_ylabel("t-SNE 2")
    plt.tight_layout()
    plt.savefig(f"{FIGURES_DIR}tsne_clusters.pdf", dpi=150)
    plt.close()

def plot_radar(centroids_raw: np.ndarray,
               cluster_names: dict[int, str]) -> None:
    N    = len(DIMENSIONS)
    angs = np.linspace(0, 2 * np.pi, N, endpoint=False).tolist()
    angs += angs[:1]
    colors = ["#e6194b", "#3cb44b", "#4363d8", "#f58231", "#911eb4", "#46f0f0", "#f032e6", "#bcf60c"]

    fig, ax = plt.subplots(figsize=(7, 7), subplot_kw=dict(polar=True))
    for ci, name in cluster_names.items():
        vals = centroids_raw[ci].tolist() + centroids_raw[ci][:1].tolist()
        ax.plot(angs, vals, color=colors[ci % len(colors)], linewidth=2, label=name)
        ax.fill(angs, vals, color=colors[ci % len(colors)], alpha=0.1)

    ax.set_xticks(angs[:-1])
    ax.set_xticklabels(DIMENSIONS, fontsize=9)
    ax.set_ylim(1, 10)
    ax.set_title("Cluster centroids (style dimensions)", pad=20)
    ax.legend(loc="upper right", bbox_to_anchor=(1.35, 1.1), fontsize=8)
    plt.tight_layout()
    plt.savefig(f"{FIGURES_DIR}radar_centroids.pdf", dpi=150)
    plt.close()

def run_phase3_clustering(input_path: str = ANNOTATED_PROMPTS_PATH,
                          output_path: str = CLUSTER_RESULTS_PATH) -> None:
    log.info("--- Starting Phase 3: Clustering ---")
    Path(FIGURES_DIR).mkdir(parents=True, exist_ok=True)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    records = []
    skipped_incomplete = 0
    with open(input_path) as fin:
        for line in fin:
            rec = json.loads(line)
            if has_complete_scores(rec):
                # Normalize to active schema/order before building the DataFrame.
                rec["scores"] = {d: int(rec["scores"][d]) for d in DIMENSIONS}
                records.append(rec)
            else:
                skipped_incomplete += 1
    if skipped_incomplete:
        log.warning(
            f"Skipped {skipped_incomplete} records without complete scores for active dimensions. "
            "Run Phase 2 again to re-annotate them."
        )
    if len(records) < 2:
        raise ValueError("Need at least 2 completely annotated prompts for clustering.")
    df      = pd.DataFrame([r["scores"] for r in records])

    check_dimension_independence(df)

    scaler   = StandardScaler()
    X_scaled = scaler.fit_transform(df[DIMENSIONS].values)

    best_k, sil_scores = grid_search_k(X_scaled)
    Path("data/silhouette_scores.json").write_text(
        json.dumps({str(k): v for k, v in sil_scores.items()}, indent=2))

    km     = KMeans(n_clusters=best_k, random_state=RANDOM_STATE, n_init=10)
    labels = km.fit_predict(X_scaled)

    if best_k > N_TOP_CLUSTERS:
        log.info(f"Merging from k={best_k} to k={N_TOP_CLUSTERS}")
        labels = merge_to_target(km, X_scaled, N_TOP_CLUSTERS)
    elif best_k < N_TOP_CLUSTERS:
        log.warning(f"Best k={best_k} < target {N_TOP_CLUSTERS}; using k={best_k}")

    n_clusters      = len(np.unique(labels))
    centroids_raw   = np.array([
        df[DIMENSIONS].values[labels == c].mean(axis=0)
        for c in range(n_clusters)
    ])
    cluster_names   = label_clusters(centroids_raw)

    plot_tsne(X_scaled, labels, cluster_names)
    plot_radar(centroids_raw, cluster_names)

    with open(output_path, "w") as fout:
        for idx, record in enumerate(records):
            record["cluster_id"]   = int(labels[idx])
            record["cluster_name"] = cluster_names[int(labels[idx])]
            fout.write(json.dumps(record, ensure_ascii=False) + "\n")

    summary = {
        int(ci): {
            "name":     cluster_names[ci],
            "size":     int((labels == ci).sum()),
            "centroid": {d: round(float(centroids_raw[ci][di]), 2)
                         for di, d in enumerate(DIMENSIONS)},
        }
        for ci in range(n_clusters)
    }
    Path("data/cluster_summary.json").write_text(json.dumps(summary, indent=2))
    log.info("Cluster summary:\n" + json.dumps(summary, indent=2))


# =============================================================================
# ── Main Entry Point ─────────────────────────────────────────────────────────
# =============================================================================

def main():
    log.info("Initializing CIIP Prompt Style Pipeline...")
    
    # Run Phase 1
    run_phase1_filtering()
    
    # Run Phase 2 (Make sure ANTHROPIC_API_KEY is exported in your environment)
    run_phase2_annotation()
    
    # Run Phase 3
    run_phase3_clustering()
    
    log.info("Pipeline completed successfully.")

if __name__ == "__main__":
    # Uncomment the phases inside main() to run them
    main()
