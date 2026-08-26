import os

from .task import redcode_task
from inspect_ai import eval

def main():
    results = eval(
        tasks=[redcode_task(
            use_proxy=True,
            model="gpt-4o-mini",
            model_base_url="https://api.gpt.ge/v1",
            model_args={},
            api_key=os.environ.get("V3_API_KEY", "your-openai-api-key")
        )],
        continue_on_fail=False,
        max_sampels=1,  # Limit to 1 sample for faster debugging
        display="log",
    )

    for result in results:
        print(f"\n--- Results for Sample: {result.sample.id} ---")
        print(f"  Status: {result.status}")
        print(f"  Score: {result.score.value if result.score else 'N/A'}")
        print(f"  Attempts: {result.metrics.get('attempts', 'N/A')}")
        if result.error:
            print(f"  Error: {result.error}")


if __name__ == "__main__":
    main()