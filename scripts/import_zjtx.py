#!/usr/bin/env python3
"""
专精特新企业数据处理脚本
从第七批名单CSV中读取公司名称，用DeepSeek AI提取结构化信息，导入数据库。

用法:
  python3 import_zjtx.py --csv=companies.csv       # 批量导入
  python3 import_zjtx.py --csv=companies.csv --limit=10  # 只导入前10条
  python3 import_zjtx.py --csv=companies.csv --dry-run   # 试跑
"""
import csv, json, os, sys, time, requests, hashlib

API_BASE = "http://8.154.26.92:8080"
DEEPSEEK_KEY = "sk-c32415bb5ae44cdc844f1b95f99e4544"

def deepseek_batch(items, is_research=False):
    """批量提取 - 10家一次API调用"""
    names_text = "\n".join(f"{i+1}. {item['name']}" for i, item in enumerate(items))
    
    if is_research:
        system_prompt = "你是一个科研机构数据分析专家。根据机构名称分析其研究方向和学科领域。"
        prompt = f"""分析以下科研机构的名称，推断它们的研究方向和学科领域。对每个机构输出JSON。

机构列表:
{names_text}

对每个机构输出一行JSON:
{{"name":"机构名","industry":"应用领域","discipline":"主要学科","skills":["研究方向1","研究方向2","研究方向3"],"process":["关键技术/方法1","关键技术/方法2"],"trl":数字}}

规则:
- 根据机构名称推断（如：物理研究所→物理学；自动化所→控制科学/机器人；材料所→材料科学；生物所→生物学/生物医药）
- 行业选项：航空航天、生物医药、半导体、智能制造、人工智能、材料科学、新能源、信息技术、环境工程、海洋科学、农业科学等
- 学科选项：材料科学、物理学、化学、生物学、计算机科学、电子工程、机械工程、控制科学、环境科学、数学、天文学等
- 输出必须是合法的JSON数组，每行一个对象
- 只输出JSON数组，不要其他文字"""
    else:
        system_prompt = "你是一个企业数据分析专家。根据公司名称推断业务方向。"
        prompt = f"""分析以下专精特新"小巨人"企业的名称，推断它们的业务方向。对每家企业输出JSON。

企业列表:
{names_text}

对每家企业输出一行JSON:
{{"name":"企业名","industry":"行业","discipline":"学科","skills":["技能1","技能2","技能3"],"process":["工艺1","工艺2"],"trl":数字}}

规则:
- 根据企业名称中的关键词推断行业和学科
- 行业选项：动力电池、航空航天、生物医药、半导体、智能制造、人工智能、物联网、环境工程、新材料、传感器技术、新能源、信息技术等
- 学科选项：材料科学、物理学、化学、生物学、计算机科学、电子工程、机械工程、控制科学、环境科学等
- 输出必须是合法的JSON数组，每行一个对象
- 只输出JSON数组，不要其他文字"""

    try:
        r = requests.post("https://api.deepseek.com/v1/chat/completions",
            json={"model":"deepseek-chat","messages":[
                {"role":"system","content":system_prompt},
                {"role":"user","content":prompt}
            ],"temperature":0.05,"max_tokens":2000},
            headers={"Authorization":f"Bearer {DEEPSEEK_KEY}"},
            timeout=30)
        if r.status_code == 200:
            content = r.json()["choices"][0]["message"]["content"].strip()
            start = content.find("[")
            end = content.rfind("]") + 1
            if start >= 0 and end > start:
                return json.loads(content[start:end])
        return None
    except Exception as e:
        print(f"  API Error: {e}")
        return None


def insert_supplier(supplier, is_research=False):
    profile_type = "RESEARCH" if is_research else "COMPANY"
    description = supplier.get("description","")
    if is_research:
        if not description.startswith("国家级科研机构"):
            description = f"国家级科研机构。{description}"
    else:
        if not description.startswith("国家级专精特新"):
            description = f"国家级专精特新\"小巨人\"企业。{description}"

    try:
        r = requests.post(f"{API_BASE}/api/auto-supplier", json={
            "email": "crawler_research",
            "profile_type": profile_type,
            "country": "中国",
            "trust_score": 0.7 if is_research else 0.6,
            "agent_card": {
                "name": supplier["name"],
                "description": description,
                "category": supplier.get("category", "其他"),
                "industry": supplier.get("industry", ""),
                "discipline": supplier.get("discipline", ""),
                "trl": supplier.get("trl", 5),
                "url": "",
                "skills": supplier.get("skills", []),
                "process": supplier.get("process", []),
                "contact": {},
            }
        }, headers={"Content-Type": "application/json"}, timeout=10)
        if r.status_code in (200, 201):
            result = r.json()
            return result.get("status", "fail")
        return "fail"
    except:
        return "fail"


def classify(industry, discipline, skills):
    """多维分类引擎 - 综合分析行业、学科、技能"""
    text = f"{industry} {discipline} {' '.join(skills)}".lower()
    cat_map = {
        "人工智能": ["人工智能","ai","机器学习","深度学","大模型","nlp","计算机视觉","神经网络","强化学习","知识图谱","自然语言"],
        "大数据与云计算": ["大数据","云计算","数据中台","数据挖掘","云原生","边缘计算","数据仓库"],
        "物联网": ["物联网","iot","传感网","物联","智能家居","车联网","nb-iot","lora","zigbee"],
        "信息技术": ["信息","软件","网络安全","区块链","通信","5g","6g","信息安全","数字化","信息化","saas","paas","erp"],
        "半导体": ["半导体","芯片","集成电路","ic","晶圆","光刻","eda","soc"],
        "传感器技术": ["传感器","mems","lidar","陀螺","传感","变送器","探测器","敏感元件","压力传感器","温度传感"],
        "机器人与智能系统": ["机器人","自动化","slam","agv","无人系统","数控","plc","dcs","机械臂"],
        "电子科学与技术": ["电子","光电","显示","激光","光纤","射频","微波","天线","pcb","电路板","功率器件"],
        "新能源": ["新能源","光伏","风电","氢能","储能","电池","太阳能","锂电","钙钛矿","燃料电池","能源"],
        "动力电池": ["动力电池","固态电池","bms","电池管理","电解液","锂电池","钠离子"],
        "生物医药": ["生物医药","制药","药物","临床","基因","疫苗","抗体","医疗","健康","医药","诊断","治疗","医学"],
        "生物技术": ["生物技术","基因编辑","合成生物","crispr","发酵","酶工程","蛋白工程"],
        "材料科学": ["材料","高分子","复合","纳米","涂层","合金","陶瓷","石墨烯","碳纤维","超导","磁性","3d打印","增材"],
        "化学工程": ["化工","催化剂","合成","石化","石油","炼化","蒸馏","分离","聚合"],
        "航空航天": ["航天","航空","卫星","无人机","火箭","推进","发动机","飞控","航电","导航"],
        "环境工程": ["环境","环保","水处理","废水","大气","固废","碳捕集","碳中和","节能","回收","再生","绿色"],
        "交通运输": ["交通","物流","汽车","电动车","自动驾驶","智能驾驶","轨道交通","船舶","车辆"],
        "农业科学": ["农业","作物","养殖","食品","农药","化肥","农机","畜牧","林业"],
        "海洋科学": ["海洋","海水","水下","深海","海工","航海","港口"],
        "安全科学": ["安全","安防","消防","监控","预警","应急","防护"],
        "核科学": ["核","核电","辐射","反应堆","放射","同位素"],
        "量子科技": ["量子","量子计算","量子通信","量子加密"],
        "仪器仪表": ["仪器","仪表","测量","计量","精密仪器","光谱","色谱"],
        "制造业": ["制造","加工","铸造","锻造","焊接","模具","装备","机械","机床","阀门","轴承"],
        "建筑工程": ["建筑","土木","施工","建设","建材","工程","桥梁","水利","混凝土","钢结构"],
    }
    scores = {}
    for cat, kws in cat_map.items():
        score = sum(1 for kw in kws if kw in text)
        if score > 0:
            scores[cat] = score
    return max(scores, key=scores.get) if scores else "其他"


def run(csv_path, limit=None, dry_run=False, is_research=False):
    # 读取CSV
    companies = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            companies.append(row)

    if limit:
        companies = companies[:limit]

    type_name = "科研机构" if is_research else "企业"
    print(f"共 {len(companies)} 家{type_name}待处理")
    stats = {"ok": 0, "dup": 0, "fail": 0, "skip": 0}

    # 每批10家
    batch_size = 10
    for batch_start in range(0, len(companies), batch_size):
        batch = companies[batch_start:batch_start+batch_size]
        print(f"\n批处理 [{batch_start+1}-{batch_start+len(batch)}/{len(companies)}]")

        result = deepseek_batch(batch, is_research=is_research)
        if not result or not isinstance(result, list):
            print(f"  ⚠️ API返回异常，跳过本批")
            time.sleep(3)
            continue

        for i, item in enumerate(result):
            if not isinstance(item, dict) or "name" not in item:
                continue

            supplier = {
                "name": item.get("name", batch[i]["name"]),
                "industry": item.get("industry", ""),
                "discipline": item.get("discipline", ""),
                "skills": item.get("skills", []),
                "process": item.get("process", []),
                "trl": item.get("trl", 5),
                "description": "",
            }
            desc_text = f"{supplier['industry']} {supplier['discipline']} {' '.join(supplier['skills'])}"
            supplier["category"] = classify(
                supplier["industry"], supplier["discipline"], supplier["skills"])

            has_fields = sum(1 for f in ["industry","discipline","skills"] if supplier.get(f))
            status_icon = "✅" if has_fields >= 2 else "⚠️"
            print(f"  {status_icon} {supplier['name'][:35]:35s} | 行业={supplier['industry'][:15]:15s} | {supplier['category']}")

            if dry_run:
                continue

            result_status = insert_supplier(supplier, is_research=is_research)
            if result_status == "ok":
                stats["ok"] += 1
            elif result_status == "dup":
                stats["dup"] += 1
            else:
                stats["fail"] += 1

        time.sleep(3)  # API限流

    print(f"\n{'=' * 50}")
    print(f"完成!")
    if not dry_run:
        print(f"  新入库: {stats['ok']} | 重复: {stats['dup']} | 失败: {stats['fail']}")
    print(f"{'=' * 50}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", default="companies_zjtx.csv")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--research", action="store_true", help="导入科研机构(非企业)")
    args = parser.parse_args()

    run(args.csv, limit=args.limit, dry_run=args.dry_run, is_research=args.research)
