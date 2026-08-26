import requests
from typing import List, Dict
LLM_TOKEN_ENDPOINT = "http://10.82.1.217:8000/tokenize"
LLM_TOKEN_MODEL = "/data/zfk/models/gemma-4-E2B-it"


def num_tokens_from_messages(
    messages: List[Dict[str, str]],
) -> int:
    """
    使用 vLLM 的 tokenize 接口精确计算 tokens（推荐）
    """
    try:
        response = requests.post(
            LLM_TOKEN_ENDPOINT,
            json={
                "model": LLM_TOKEN_MODEL,
                "messages": messages,   # 直接传 messages，最准确（会走 chat template）
                # "prompt": "..."       # 也可以直接传 prompt
            },
            timeout=10
        )
        response.raise_for_status()
        data = response.json()
        
        # vLLM 返回的结构通常包含 "length" 或 "token_ids"
        return data.get("count") or len(data.get("tokens", []))
    
    except Exception as e:
        print(f"Tokenize API 调用失败: {e}，回退到近似计算")
        def approximate_token_count(messages: List[Dict[str, str]]) -> int:
            """
            简单的近似计算（回退方案）
            中文约 1 token ≈ 1.8~2 个字符，英文约 1 token ≈ 4 个字符
            """
            total_chars = 0
            for msg in messages:
                content = msg.get("content", "")
                if isinstance(content, list):   # 处理多模态 content（含图片等）
                    for item in content:
                        if isinstance(item, dict) and item.get("type") == "text":
                            total_chars += len(item.get("text", ""))
                else:
                    total_chars += len(str(content))
            
            # 中文为主时用这个系数，混合时可以调
            return int(total_chars / 1.8) + 10   # 略微多估一点更安全
        return approximate_token_count(messages)  # 下面有回退函数