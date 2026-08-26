import json
import re
import os
import pdb
os.environ["https_proxy"] = "http://10.214.99.83:7897"
"""
攻击数据集语义去重脚本
流程: 精确哈希去重 → 语义向量去重 (faiss ANN)
"""

import hashlib
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.neighbors import NearestNeighbors



# ──────────────────────────────────────────────
# 1. 语义指纹构建
# ──────────────────────────────────────────────

def extract_placeholder_semantics(record: dict) -> str:
    """
    从 metadata.input_arguments 提取 placeholder 的语义描述，
    替代 #{var_name} 这种无意义的占位符。
    返回形如:
        [command_to_add: Command to add to the .bash_profile file (string)]
    """
    args = record.get("metadata", {}).get("input_arguments", {})
    if not args:
        return ""
    parts = []
    for var, info in args.items():
        desc = info.get("description", "")
        typ  = info.get("type", "")
        parts.append(f"[{var}: {desc} ({typ})]")
    return " ".join(parts)


def build_semantic_text(record: dict) -> str:
    """
    构建用于向量化的语义指纹。
    - 对 Atomic Test：用 placeholder 语义描述替换 #{...}
    - 对纯分类/纯 example 条目：尽量利用所有有效字段
    权重通过重复拼接体现（payload/example 最重要）
    """
    parts = []

    # category 和 craft 作为高权重的分类信号
    for field in ("category", "craft"):
        val = record.get(field, "")
        if isinstance(val, str) and val.strip():
            parts.append(val.strip())

    # description
    desc = record.get("description", "") or record.get("metadata", {}).get("description", "")
    if isinstance(desc, str) and desc.strip():
        parts.append(desc.strip())

    # payload：若含 placeholder，追加变量语义；否则直接用原文
    payload = record.get("payload", "")
    if isinstance(payload, str) and payload.strip():
        placeholder_sem = extract_placeholder_semantics(record)
        if placeholder_sem:
            # 用变量语义替换 #{var}，让向量模型理解真实意图
            cleaned_payload = re.sub(r"#\{[^}]+\}", "__PLACEHOLDER__", payload)
            parts.append(cleaned_payload.strip())
            parts.append(placeholder_sem)          # 额外加入语义描述
        else:
            parts.append(payload.strip())
        parts.append(payload.strip())              # payload 重复一次提权重

    # example（重复一次提权重）
    example = record.get("example", "")
    if isinstance(example, str) and example.strip():
        parts.append(example.strip())
        parts.append(example.strip())

    # abbr 作为来源背景信号（放最后，权重低）
    abbr = record.get("abbr", "")
    if isinstance(abbr, str) and abbr.strip():
        parts.append(abbr.strip())

    return "\n".join(parts)


# ──────────────────────────────────────────────
# 2. 质量评分
# ──────────────────────────────────────────────

def quality_score(record: dict) -> int:
    score = 0
    payload = record.get("payload", "").strip()
    example = record.get("example", "").strip()

    # 字段完整度
    field_weights = [
        ("payload", 10), ("example", 8), ("description", 5),
        ("hidden_strategy", 4), ("craft", 3), ("category", 2),
    ]
    for field, w in field_weights:
        if record.get(field, "").strip():
            score += w

    # payload/example 内容质量
    for text in (payload, example):
        if len(text) > 50:  score += 3
        if len(text) > 200: score += 3
        if re.search(r'[<>{}\[\]\'";`\\]', text): score += 4  # 含特殊字符，像真实 payload

    # 有 placeholder 语义说明的 atomic-test 额外加分
    if record.get("metadata", {}).get("input_arguments"):
        score += 3

    return score


# ──────────────────────────────────────────────
# 3. 精确哈希去重
# ──────────────────────────────────────────────

def exact_dedup(records: list[dict]) -> list[dict]:
    """基于 payload+example+description 的 MD5 精确去重，保留先出现的条目。"""
    seen: set[str] = set()
    unique: list[dict] = []
    for r in records:
        key_src = (
            r.get("payload", "").strip()
            + r.get("example", "").strip()
            + r.get("description", "").strip()
        )
        if not key_src:          # 全空条目直接保留（等语义去重处理）
            unique.append(r)
            continue
        h = hashlib.md5(key_src.encode()).hexdigest()
        if h not in seen:
            seen.add(h)
            unique.append(r)
    return unique

# ──────────────────────────────────────────────
# 4. 语义去重（faiss ANN）
# ──────────────────────────────────────────────

def semantic_dedup(
    records: list[dict],
    model: SentenceTransformer,
    threshold: float = 0.88,
    top_k: int = 20,
) -> list[dict]:

    infos = []

    for idx, r in enumerate(records):
        sem = build_semantic_text(r)

        if sem.strip():
            infos.append({
                "record": r,
                "sem": sem,
                "score": quality_score(r),
                "idx": idx,
            })

    if not infos:
        return records

    print(f"  [*] 向量化 {len(infos)} 条数据...")

    texts = [info["sem"] for info in infos]

    embeddings = model.encode(
        texts,
        batch_size=64,
        show_progress_bar=True,
        normalize_embeddings=True,
    )

    embeddings = np.asarray(embeddings, dtype=np.float32)

    print(f"  [*] KNN 搜索 (top_k={top_k})...")

    knn = NearestNeighbors(
        n_neighbors=min(top_k + 1, len(infos)),
        metric="cosine",
        algorithm="brute",
    )

    knn.fit(embeddings)

    distances, neighbors = knn.kneighbors(embeddings)

    # sklearn cosine distance:
    # distance = 1 - cosine_similarity
    similarities = 1.0 - distances

    to_drop: set[int] = set()
    dupe_count = 0

    for i, (sims, nbrs) in enumerate(zip(similarities, neighbors)):

        if i in to_drop:
            continue

        for sim, j in zip(sims, nbrs):

            if j <= i or j in to_drop:
                continue

            if sim >= threshold:

                dupe_count += 1

                rec_i, rec_j = infos[i], infos[j]

                print(
                    f"    [dup] sim={sim:.3f} "
                    f"| A(s={rec_i['score']}): "
                    f"{rec_i['sem'][:60].replace(chr(10), ' ')}... "
                    f"| B(s={rec_j['score']}): "
                    f"{rec_j['sem'][:60].replace(chr(10), ' ')}..."
                )

                if rec_i["score"] >= rec_j["score"]:
                    to_drop.add(j)
                else:
                    to_drop.add(i)
                    break

    print(f"  [*] 语义重复: {dupe_count} 对，丢弃 {len(to_drop)} 条")

    return [
        infos[i]["record"]
        for i in range(len(infos))
        if i not in to_drop
    ]


# ──────────────────────────────────────────────
# 5. 主流程
# ──────────────────────────────────────────────

def deduplicate(input_path: str, output_path: str, threshold: float = 0.88):
    print(f"[*] 加载: {input_path}")
    with open(input_path, "r", encoding="utf-8") as f:
        ori_dataset: list[dict] = json.load(f)
    print(f"[*] 原始数据: {len(ori_dataset)} 条")

    dataset = [r for r in ori_dataset if r['suitable']]

    # Step 1: 精确去重
    after_exact = exact_dedup(dataset)
    print(f"[*] 精确去重后: {len(after_exact)} 条 (去除 {len(dataset) - len(after_exact)} 条)")

    # Step 2: 语义去重
    print("[*] 加载向量模型...")
    model = SentenceTransformer("all-MiniLM-L6-v2")
    after_semantic = semantic_dedup(after_exact, model, threshold=threshold)
    print(f"[*] 语义去重后: {len(after_semantic)} 条 (去除 {len(after_exact) - len(after_semantic)} 条)")

    # 保存
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(after_semantic, f, indent=2, ensure_ascii=False)
    print(f"[*] 已保存至: {output_path}")
    print(f"[*] 总计去除: {len(dataset) - len(after_semantic)} 条 / 原始 {len(dataset)} 条")


if __name__ == "__main__":
    INPUT  = "dataset_gen/raw_attacks.json"
    OUTPUT = "dataset_gen/clean_dataset.json"
    THRESHOLD = 0.88   # 可调：0.88-0.92，越高越保守（少删）

    if os.path.exists(INPUT):
        deduplicate(INPUT, OUTPUT, THRESHOLD)
    else:
        print(f"[!] 找不到输入文件: {INPUT}")
