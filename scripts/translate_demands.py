"""
用 DeepSeek 批量翻译英文需求为中文
并修复 researcher_support_crawler.py 自动翻译
"""
import urllib.request, json, time, sys

API = "http://demand-chain.duckdns.org:8080"
DEEPSEEK_KEY = "sk-c32415bb5ae44cdc844f1b95f99e4544"

def is_mostly_english(text):
    if not text: return False
    en = sum(1 for c in text if c.isascii() and c.isalpha())
    cn = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    total = en + cn
    if total == 0: return False
    return en / total > 0.6

def translate(text, max_retries=2):
    """用 DeepSeek 把英文翻译成中文"""
    for attempt in range(max_retries):
        try:
            payload = json.dumps({
                "model": "deepseek-chat",
                "messages": [
                    {"role": "system", "content": "你是一个翻译助手。把下面的英文翻译成中文。只输出翻译结果，不要附加任何说明。"},
                    {"role": "user", "content": text[:500]}
                ],
                "temperature": 0.1,
                "max_tokens": 300
            }).encode("utf-8")
            req = urllib.request.Request(
                "https://api.deepseek.com/v1/chat/completions",
                data=payload,
                headers={
                    "Authorization": f"Bearer {DEEPSEEK_KEY}",
                    "Content-Type": "application/json"
                }
            )
            with urllib.request.urlopen(req, timeout=30) as r:
                result = json.loads(r.read())
                translated = result["choices"][0]["message"]["content"].strip()
                if translated:
                    return translated
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(3)
    return text  # fallback: 返回原文

# ============================================
# 第1步：翻译已有英文需求
# ============================================
print("=" * 60)
print("第1步：翻译已有英文需求")
print("=" * 60)

# 拉取所有需求
items = json.loads(urllib.request.urlopen(
    urllib.request.Request(f"{API}/api/demands?page=1&per_page=200")
).read())
demands = items.get("items", [])

en_demands = []
for d in demands:
    text = d.get("raw_text", "")
    if is_mostly_english(text):
        # 跳过已经是中英混合的旧系统数据
        has_cn = any('\u4e00' <= c <= '\u9fff' for c in text[:50])
        if has_cn and len(text) > 80:
            continue  # 已经是中英双语，保留
        en_demands.append((d["id"], text, d.get("category","")))

print(f"需要翻译的英文需求: {len(en_demands)} 条\n")

translated_count = 0
skip_count = 0
for did, text, cat in en_demands:
    print(f"  原文: {text[:60]}...")
    cn = translate(text)
    if cn and cn != text:
        print(f"  译文: {cn[:60]}")
        # 入库新翻译后的版本（作为新需求，因为原需求没有update API）
        payload = json.dumps({
            "raw_text": cn[:500],
            "category": cat,
            "email": "crawler",
            "source": "翻译（原英文需求）",
        }).encode("utf-8")
        try:
            req = urllib.request.Request(f"{API}/api/auto-demand",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=10) as r:
                result = json.loads(r.read())
                if result.get("status") == "ok":
                    translated_count += 1
                    print(f"      ✅ 已入库翻译版")
                elif result.get("status") == "dup":
                    skip_count += 1
                    print(f"      ⏭ 重复")
        except:
            pass
    print()
    time.sleep(1.5)  # 控制API频率

print(f"\n翻译完成: {translated_count} 条入库, {skip_count} 条重复")
print(f"（原英文需求保留在数据库中待后续清理）")


