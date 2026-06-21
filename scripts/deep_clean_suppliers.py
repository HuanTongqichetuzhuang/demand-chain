"""深度清理 SelectScience 网站的导航/分类页（非公司）"""
import urllib.request, json, time

API = "http://8.154.26.92:8080"
headers = {"Content-Type": "application/json"}
email_body = json.dumps({"email": "477570216@qq.com"}).encode()

def get_all():
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

def delete_supplier(sid, name):
    try:
        req = urllib.request.Request(f"{API}/api/admin/suppliers/{sid}", 
            data=email_body, headers=headers, method="DELETE")
        with urllib.request.urlopen(req, timeout=5) as r:
            return json.loads(r.read()).get("status") == "deleted"
    except:
        return False

# 明确不是公司的导航/功能页面 — 这些可以安全删除
NAV_NAMES = {n.lower() for n in [
    "Insights for Marketers", "Request Pricing",
    "Contact Us", "Testimonials",
    "Newsletter", "Subscribe", "White Papers",
    "Get Support", "Support Hub", "Sign In",
    "Register", "Quick Order", "My Account",
    "Cart", "Checkout",
    "Services and Support", "On-Demand Webinars",
    "Technical Library", "Product Resources",
    "Troubleshooting", "FAQs", "User Guides",
    "Submit Your Paper", "Author Guidelines", "Peer Review",
    "Open Access", "Reprints", "Advertise",
    "About Us", "Our Team", "Careers", "Press",
    "Investors", "Partners", "Distributors",
    "Dealer Login", "Portal",
    "Knowledge Center", "Resource Center", "Learning Center", "Community",
    "Blog", "Forum", "Reviews",
    "Downloads", "Software", "Mobile App",
    "API", "Integrations", "Marketplace",
    "Featured Products", "New Products", "Top Sellers", "Promotions",
    # 更多 SelectScience 功能页
    "Sample Preparation", "Method Development",
    "Bioanalysis", "Small Molecules",
    "Cell Analysis", "Lab Services",
    "Quality Control", "Lab Automation",
]}

def is_nav_name(name):
    return name.strip().lower() in NAV_NAMES

print("获取供应商列表...")
suppliers = get_all()
print(f"共 {len(suppliers)} 个\n")

to_delete = []

for s in suppliers:
    sid = s.get("id", "")
    name = s.get("name", "") or ""
    url = s.get("url", "") or s.get("agent_card", {}).get("url", "") or ""
    desc = s.get("description", "") or s.get("agent_card", {}).get("description", "") or ""
    contact = s.get("contact", {}) or s.get("agent_card", {}).get("contact", {}) or {}
    industry = s.get("industry", "") or s.get("agent_card", {}).get("industry", "") or ""
    skills = s.get("skills", []) or s.get("agent_card", {}).get("skills", []) or []
    has_email = bool(contact.get("email", "") if isinstance(contact, dict) else False)
    
    # 导航/分类页
    if is_nav_name(name):
        to_delete.append((sid, name, "导航名"))
        continue
    
    # SelectScience 页面：没有URL + 没有邮箱 + 通用行业 "科学仪器/实验设备"
    if (not url and not has_email and "科学仪器" in industry and 
        ("实验室设备" in desc or desc == "科学仪器/实验室设备供应商" or 
         desc == "实验室设备供应商" or not desc)):
        if not skills or skills == ["科学仪器", "实验设备"] or skills == ["科学仪器供应", "实验室设备"]:
            to_delete.append((sid, name[:40], f"无URL+无联系方式+通用描述"))
            continue

print(f"待删除: {len(to_delete)} 个\n")

ok = 0
for sid, name, reason in to_delete:
    if delete_supplier(sid, name):
        print(f"  ✅ 已删 [{reason}] {name[:40]}")
        ok += 1
    else:
        print(f"  ❌ 删除失败 {name[:40]}")
    time.sleep(0.15)

print(f"\n已删除: {ok}/{len(to_delete)}")
print(f"剩余供应商: {len(suppliers) - ok} (约)")
