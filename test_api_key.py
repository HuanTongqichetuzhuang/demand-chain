"""测试 API Key 是否有效"""
import asyncio
import httpx
import os
import sys
sys.path.insert(0, ".")


async def test_key():
    api_key = os.getenv("TEST_API_KEY", "").strip()
    if not api_key:
        print("ERROR: 通过环境变量传入: set TEST_API_KEY=sk-xxx && python test_key.py")
        return

    url = "https://api.deepseek.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    body = {
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": "回复OK"}],
        "max_tokens": 5,
    }

    print(f"正在测试 Key: {api_key[:20]}...")
    async with httpx.AsyncClient(timeout=20) as client:
        try:
            resp = await client.post(url, json=body, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                print(f"SUCCESS (200): 模型返回 '{content}'")
                print(f"余额: {resp.headers.get('x-ds-account-status', 'N/A')}")
            else:
                print(f"FAIL ({resp.status_code}): {resp.text[:200]}")
        except Exception as e:
            print(f"NETWORK ERROR: {e}")


if __name__ == "__main__":
    asyncio.run(test_key())
