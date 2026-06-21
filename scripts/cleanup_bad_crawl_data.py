"""
清理 researcher_support_crawler.py 导入的低质量数据
然后重写爬虫代码，只保留能产出干净数据的源
"""
import urllib.request, json, time

API = "http://demand-chain.duckdns.org:8080"
ADMIN_EMAIL = "477570216@qq.com"

def fetch(endpoint, max_pages=5):
    items = []
    for page in range(1, max_pages + 1):
        try:
            req = urllib.request.Request(f"{API}{endpoint}?page={page}&per_page=200")
            data = json.loads(urllib.request.urlopen(req, timeout=10).read())
            batch = data.get("items", [])
            if not batch: break
            items.extend(batch)
        except: break
    return items

def api_del(endpoint, eid):
    payload = json.dumps({"email": ADMIN_EMAIL}).encode("utf-8")
    req = urllib.request.Request(f"{API}{endpoint}/{eid}", data=payload,
        headers={"Content-Type": "application/json"}, method="DELETE")
    try:
        urllib.request.urlopen(req, timeout=5)
        return True
    except: return False

print("= 第一步：找出所有低质量数据 =\n")

demands = fetch("/api/demands")
suppliers = fetch("/api/suppliers")

# P0: 淘汰的需求 — ERC/UKRI 首页导航链接、研究理事会名称
bad_demand_sources = ["ERC欧洲研究委员会资助", "UKRI英国研究与创新资助"]
bad_demand_texts = [
    "Apply for funding", "Manage your award", "Getting your funding",
    "ERC President", "ERC Executive Agency", "ERC legal basis",
    "ERC for Ukraine", "ERC Research Information System",
    "ERC at a glance", "ERC publications",
    "Mapping ERC frontier research",
    "Improving your funding experience",
]

to_del_demands = []
for d in demands:
    text = d.get("raw_text","").strip()
    source = d.get("source","") or ""
    if source in bad_demand_sources:
        # 保留真实资助机会（文本较长且有具体内容）
        if len(text) < 40 or any(t in text for t in bad_demand_texts):
            to_del_demands.append((d["id"], text[:50], source[:15]))
            continue
    # 中国技术交易所的机构名称（不是技术成果）
    if "技术成果转化" in text and len(text) < 40:
        to_del_demands.append((d["id"], text[:50], "机构名非成果"))

# P2: 淘汰的供应商 — IP.com 导航页、cailiao 噪声
to_del_suppliers = []
for s in suppliers:
    name = s.get("name","").strip()
    # cailiao 的非科研产品
    if "饲料" in name or "屠宰" in name or "包装印刷" in name or "POS机" in name or "收款" in name:
        to_del_suppliers.append((s["id"], name[:40], "非科研产品"))
        continue
    # IP.com 导航
    ip_nav = ["InnovationQ+", "Technology Vitality Report", "Patent Vitality Report",
              "Patentability Search Services", "Patent Landscape", "Innovation Lifecycle",
              "Patent Invalidity", "Technology & Engineering"]
    if name in ip_nav:
        to_del_suppliers.append((s["id"], name[:40], "IP导航页"))
        continue

print(f"待删除低质量需求: {len(to_del_demands)} 条")
for _, t, r in to_del_demands:
    print(f"  ❌ [{r}] {t}")
print(f"\n待删除低质量供应商: {len(to_del_suppliers)} 个")
for _, n, r in to_del_suppliers:
    print(f"  ❌ [{r}] {n}")

print(f"\n= 第二步：执行删除 =\n")
ok_d = sum(1 for eid,_,_ in to_del_demands if api_del("/api/admin/demands", eid))
ok_s = sum(1 for eid,_,_ in to_del_suppliers if api_del("/api/admin/suppliers", eid))
print(f"需求删除: {ok_d}/{len(to_del_demands)}")
print(f"供应商删除: {ok_s}/{len(to_del_suppliers)}")

time.sleep(2)
req = urllib.request.Request(f"{API}/api/admin/stats")
final = json.loads(urllib.request.urlopen(req).read())
print(f"\n清理后: demands={final['demands']}, suppliers={final['suppliers']}, matches={final['matches']}")


