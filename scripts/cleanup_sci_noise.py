import urllib.request, json, time, sys

API = "http://demand-chain.duckdns.org:8080"

# 噪声关键词 — 这类"供应商"实际上不是公司
JUNK_PATTERNS = [
    # 导航/UI文字
    "Question & Answer Forums", "View / Reply", "Getting Started", "Who We Are",
    "Contact Us", "About Us", "Careers", "Videos", "All Products",
    "Request Pricing", "Testimonials", "Editorial Features",
    "Data Sharing Annex", "Corporate Social Responsibility",
    "SelectScience", "Infographics", "TechTalks", "eBooks",
    "How-to-Buy", "Content Examples",
    # 学科分类名（非公司）
    "Clinical Development", "Clinical Diagnostics", "Clinical CE",
    "Basic Research", "Drug Manufacturing", "Lead Discovery",
    "Target Discovery", "Life Sciences", "Lab Informatics",
    "General Lab", "Food and Beverage", "Environmental",
    "Cancer research", "Biopharmaceuticals", "Cannabis Testing",
    "Cell and gene therapy", "Immersive Content",
    # 无意义的短名称
    "AACR", "ASMS", "PFAS", "StatLab", "CLINICAL24",
    "Forensics", "Insights for Marketers",
    # 中国计量院噪声
    "中国计量院第十六届科技周", "中国计量院举办实验室开放日",
    "中国计量院召开", "中国计量院开展五四",
    "中国计量院访问", "世界计量日", "中德计量合作",
    "中国计量院研究员", "中国计量院承办",
    "中国计量院在CCL", "关于举办2026年注册计量师",
    "百年海魂交响",
]

# 从API拉取
def fetch_suppliers(max_pages=5):
    items = []
    for page in range(1, max_pages + 1):
        try:
            req = urllib.request.Request(f"{API}/api/suppliers?page={page}&per_page=200")
            resp = urllib.request.urlopen(req, timeout=10)
            data = json.loads(resp.read())
            batch = data.get("items", [])
            if not batch: break
            items.extend(batch)
        except: break
    return items

print("扫描所有供应商中...")
suppliers = fetch_suppliers(10)
print(f"共 {len(suppliers)} 个供应商\n")

# 识别噪声
to_delete = []
for s in suppliers:
    name = s.get("name", "")
    # 完全匹配
    if name in JUNK_PATTERNS:
        to_delete.append((s["id"], name[:50], "导航/UI/分类"))
        continue
    # 部分匹配
    for pat in JUNK_PATTERNS:
        if len(pat) > 10 and pat in name:
            to_delete.append((s["id"], name[:50], f"含:{pat[:20]}"))
            break

print(f"需要删除的噪声供应商: {len(to_delete)} 个\n")

# 按类型分类
from collections import Counter
types = Counter(t[2] for t in to_delete)
for t, cnt in types.most_common():
    print(f"  {t}: {cnt}个")

print()

# 执行删除
ADMIN_EMAIL = "477570216@qq.com"
ok, fail = 0, 0
for sid, name, reason in to_delete:
    try:
        payload = json.dumps({"email": ADMIN_EMAIL}).encode("utf-8")
        req = urllib.request.Request(
            f"{API}/api/admin/suppliers/{sid}",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="DELETE"
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            ok += 1
    except:
        fail += 1
    time.sleep(0.2)

print(f"\n删除完成: {ok} 成功, {fail} 失败")


