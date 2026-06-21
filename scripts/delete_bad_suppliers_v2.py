"""删除不合格供应商：导航名/产品页/会议通知"""
import urllib.request, json, time

API = "http://8.154.26.92:8080"
headers = {"Content-Type": "application/json"}
email_body = json.dumps({"email": "477570216@qq.com"}).encode()

def get_all_suppliers():
    items = []
    for page in range(1, 20):
        try:
            req = urllib.request.Request(f"{API}/api/suppliers?page={page}&per_page=200")
            with urllib.request.urlopen(req, timeout=10) as r:
                batch = json.loads(r.read()).get("items", [])
                if not batch: break
                items.extend(batch)
        except: break
    return items

def del_supplier(sid, name):
    try:
        req = urllib.request.Request(f"{API}/api/admin/suppliers/{sid}", 
            data=email_body, headers=headers, method="DELETE")
        with urllib.request.urlopen(req, timeout=5) as r:
            result = json.loads(r.read())
            return result.get("status") == "deleted"
    except:
        return False

# 非公司名的黑名单
NAV_NAMES = set(n.lower() for n in [
    "Target Discovery", "TechTalks", "Clinical Diagnostics", "Materials",
    "Clinical CE Webinars", "Webinars", "Videos", "Editorial features",
    "ADLM", "StatLab", "Editorial Features", "Data Sharing Annex",
    "AACR", "Case Studies", "Cannabis Testing", "Question & Answer Forums",
    "Question &amp; Answer Forums",
])

print("获取供应商列表...")
suppliers = get_all_suppliers()
print(f"共 {len(suppliers)} 个\n")

to_delete = []

for s in suppliers:
    sid = s.get("id", "")
    name = s.get("name", "") or ""
    url = s.get("url", "") or s.get("agent_card", {}).get("url", "") or ""
    nl = name.lower().strip()
    
    # 1. 导航/分类名
    if nl in NAV_NAMES:
        to_delete.append((sid, name, "导航名"))
        continue
    
    # 2. cailiao产品页（非公司）
    if "cailiao.com" in url and ("supply/" in url or "purchase/" in url):
        to_delete.append((sid, name[:50], "产品页"))
        continue
    
    # 3. 会议/论坛通知
    if any(k in name for k in ["大会", "会议通知", "论坛", "庆典", "研讨会"]):
        if "caia.org.cn" in url or "scimeeting" in url:
            to_delete.append((sid, name[:50], "会议通知"))
            continue

print(f"待删除: {len(to_delete)} 个\n")

ok = 0
for sid, name, reason in to_delete:
    if del_supplier(sid, name):
        print(f"  ✅ 已删 [{reason}] {name[:40]}")
        ok += 1
    else:
        print(f"  ❌ 删除失败 {name[:40]}")
    time.sleep(0.2)

print(f"\n已删除: {ok}/{len(to_delete)}")
