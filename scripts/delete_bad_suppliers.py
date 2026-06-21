"""Delete the remaining bad suppliers"""
import urllib.request, json, time

API = "http://8.154.26.92:8080"
headers = {"Content-Type": "application/json"}

BAD_SUPPLIER_NAMES = [
    "Top 55 Wind Energy startups",
    "Climate Tech Startups To Watch In 2026",
    "EnergyStartups",
    "ADD STARTUP",
    "Methanol Fuel startups",
    "ENERGY STARTUPS BY COUNTRY",
    "Ammonia Fuel startups",
    "Add Startup",
    "Advertising",
    "PROMOTE STARTUP",
    "Load More Startups",
    "Electric Vehicle Charging startups",
    "Battery Swapping startups",
]

# Get all suppliers
try:
    req = urllib.request.Request(f"{API}/api/suppliers?per_page=200")
    with urllib.request.urlopen(req, timeout=15) as r:
        data = json.loads(r.read())
        items = data.get("items", [])
        print(f"Got {len(items)} suppliers")
        
        email_body = json.dumps({"email": "477570216@qq.com"}).encode()
        deleted = 0
        
        for s in items:
            name = s.get("name", "")
            sid = s.get("id", "")
            
            if name in BAD_SUPPLIER_NAMES:
                try:
                    req2 = urllib.request.Request(f"{API}/api/admin/suppliers/{sid}", 
                        data=email_body, headers=headers, method="DELETE")
                    with urllib.request.urlopen(req2, timeout=5) as r2:
                        result = json.loads(r2.read())
                        if result.get("status") == "deleted":
                            print(f"  ✅ 已删 {name}")
                            deleted += 1
                        else:
                            print(f"  ❌ 删除失败 {name}: {result}")
                except urllib.error.HTTPError as e:
                    print(f"  ❌ 删除失败 {name}: {e.code}")
                except Exception as e:
                    print(f"  ❌ 删除失败 {name}: {e}")
                time.sleep(0.2)
        
        print(f"\n已删除: {deleted}/{len(BAD_SUPPLIER_NAMES)}")
        
except Exception as e:
    print(f"Error: {e}")
