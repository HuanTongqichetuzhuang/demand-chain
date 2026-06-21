#!/usr/bin/env python3
"""
需求链平台 — 智能分类引擎 v1
自动将供应商/科研机构按行业和学科精确分类。

用法:
  python3 auto_classify.py                    # 分类所有供应商
  python3 auto_classify.py --dry-run           # 试跑，只显示不改
  python3 auto_classify.py --category=传感器技术  # 只处理特定分类

流程:
1. 从API获取所有供应商
2. 综合分析 industry + discipline + skills + name + description
3. 用加权评分确定最佳分类
4. 批量更新数据库
"""
import json, sys, time
from collections import Counter

API_BASE = "http://demand-chain.duckdns.org:8080"
BATCH_SIZE = 50  # 每批更新数

# ============================================================
# 分类主表 — 多维度关键词
# ============================================================
# 每个分类有4个子维度，分别匹配不同的字段
CATEGORIES = {
    "人工智能": {
        "keywords": ["人工智能","ai","机器学习","深度学","大模型","nlp","自然语言","计算机视觉",
                     "图像识别","语音识别","推荐系统","知识图谱","强化学习","神经网络","ml","llm"],
        "industry_kw": ["人工智能","ai","ml","llm","大模型","深度学习"],
        "discipline_kw": ["人工智能","计算机科学/ai","计算机科学ai","机器学习"],
    },
    "大数据与云计算": {
        "keywords": ["大数据","云计算","云平台","数据中台","数据挖掘","数据分析","数据仓库","数据湖",
                     "云原生","边缘计算","数据集成","数据处理","数据服务"],
        "industry_kw": ["大数据","云计算","云服务","数据"],
        "discipline_kw": ["计算机科学","数据科学","数据工程"],
    },
    "物联网": {
        "keywords": ["物联网","iot","rfid","传感网","物联","智慧城市","智能家居","智能楼宇",
                     "车联网","nb-iot","lora","zigbee","穿戴设备"],
        "industry_kw": ["物联网","iot","物联"],
        "discipline_kw": ["物联网","通信工程"],
    },
    "信息技术": {
        "keywords": ["信息","软件","网络安全","区块链","通信","5g","6g","信息化","数字化",
                     "it","运维","管理系统","erp","saas","paas","信息安全","云计算安全",
                     "身份认证","加密","防火墙","入侵检测","漏洞扫描"],
        "industry_kw": ["信息技术","信息","软件","通信","网络安全","数字化"],
        "discipline_kw": ["计算机科学","信息","软件工程","通信","网络安全"],
    },
    "半导体": {
        "keywords": ["半导体","芯片","集成电路","ic","晶圆","封装","测试","流片",
                     "mosfet","cmos","摩尔","光刻","eda","ip核","soc","fpg"],
        "industry_kw": ["半导体","芯片","集成电路","ic","晶圆"],
        "discipline_kw": ["半导体","微电子","电子科学与技术","集成电路"],
    },
    "传感器技术": {
        "keywords": ["传感器","检测","mems","lidar","radar","陀螺","传感","变送器",
                     "探测器","敏感元件","生物传感器","气体传感器","压力传感器","温度传感"],
        "industry_kw": ["传感器","传感","检测"],
        "discipline_kw": ["传感器","物理学","电磁学"],
    },
    "机器人与智能系统": {
        "keywords": ["机器人","自动化","slam","导航","agv","无人系统","机械臂","协作机器人",
                     "工业机器人","服务机器人","智能控制","plc","dcs","scada","数控"],
        "industry_kw": ["机器人","自动化","智能制造","工业自动化"],
        "discipline_kw": ["机器人","控制科学","机械","自动化"],
    },
    "电子科学与技术": {
        "keywords": ["电子","光电","显示","led","oled","激光","红外","紫外","光学",
                     "光纤","光通信","光模块","功率器件","电力电子","电磁兼容","射频",
                     "微波","天线","雷达","电子元件","pcb","电路板"],
        "industry_kw": ["电子","光电","光学","显示","激光","射频"],
        "discipline_kw": ["电子","光学","电磁学","电子工程"],
    },
    "新能源": {
        "keywords": ["新能源","光伏","风电","氢能","储能","电池","太阳能","锂电","钠电",
                     "钙钛矿","燃料电池","核能","生物质能","地热","充电","换电","能源管理"],
        "industry_kw": ["新能源","光伏","电池","储能","氢能","能源"],
        "discipline_kw": ["新能源","能源","化学","电气"],
    },
    "动力电池": {
        "keywords": ["锂电","固态电池","动力电池","电池包","bms","电池管理","电解液",
                     "正极","负极","隔膜","锂电池","钠离子","刀片电池","ctp","ctc"],
        "industry_kw": ["动力电池","锂电池","电池"],
        "discipline_kw": ["材料科学/化学","化学","电化学"],
    },
    "生物医药": {
        "keywords": ["生物医药","制药","药物","临床","基因","诊断","疫苗","抗体",
                     "蛋白","多肽","细胞治疗","基因治疗","cdmo","cro","创新药",
                     "仿制药","中药","生物药","化药","医学","医疗","健康",
                     "癌症","肿瘤","糖尿病","心血管","病毒","检测试剂"],
        "industry_kw": ["生物医药","制药","医药","药物","医疗","健康","临床"],
        "discipline_kw": ["生物医药","生物","医学","药学","临床"],
    },
    "生物技术": {
        "keywords": ["生物技术","基因编辑","合成生物","crispr","发酵","酶工程","蛋白工程",
                     "生物工程","生物信息","基因组","蛋白组","代谢工程","微生物"],
        "industry_kw": ["生物技术","基因","合成生物","生物工程"],
        "discipline_kw": ["生物技术","生物","遗传","基因"],
    },
    "材料科学": {
        "keywords": ["材料","高分子","复合材料","纳米","涂层","合金","陶瓷","纤维",
                     "石墨烯","碳纤维","超导","磁性","催化剂","薄膜","塑料","橡胶",
                     "粘接","涂料","密封","金属","非晶","增材","3d打印"],
        "industry_kw": ["材料","新材料","高分子","纳米","复合"],
        "discipline_kw": ["材料科学","材料","高分子","化学"],
    },
    "化学工程": {
        "keywords": ["化工","催化剂","合成","反应","化学工程","石化","石油化工","聚合",
                     "精细化工","化工产品","化工原料","石油","炼化","蒸馏","分离"],
        "industry_kw": ["化工","石化","化学工程","石油"],
        "discipline_kw": ["化学工程","化学","化工"],
    },
    "航空航天": {
        "keywords": ["航天","航空","卫星","无人机","飞机","火箭","推进","发动机",
                     "航电","飞控","导航","空间站","探测器","星链","航天器",
                     "航空器","飞行器","机载","机载","航空航","太空"],
        "industry_kw": ["航天","航空","卫星","无人机","飞机","火箭"],
        "discipline_kw": ["航空航天","航空","航天","控制科学"],
    },
    "环境工程": {
        "keywords": ["环境","环保","水处理","废水","污水","大气","固废","土壤",
                     "生态","碳捕集","碳中和","减排","节能","回收","再生",
                     "清洁","绿色","污染","治理","排放"],
        "industry_kw": ["环境","环保","水处理","碳中和","节能"],
        "discipline_kw": ["环境","生态","环境科学"],
    },
    "交通运输": {
        "keywords": ["交通","物流","汽车","电动车","自动驾驶","智能驾驶","轨道交通",
                     "高铁","地铁","公路","桥梁","隧道","港口","船舶","航运",
                     "运输","车辆","底盘","车身","发动机","变速箱","车灯"],
        "industry_kw": ["交通","汽车","物流","轨道","船舶"],
        "discipline_kw": ["交通","机械","车辆工程","控制"],
    },
    "农业科学": {
        "keywords": ["农业","作物","养殖","食品","植物","农药","化肥","种子",
                     "农机","畜牧","水产","林业","农产品","食品加工","保鲜"],
        "industry_kw": ["农业","食品","畜牧","种植"],
        "discipline_kw": ["农业","食品","生物"],
    },
    "海洋科学": {
        "keywords": ["海洋","海水","渔业","船舶","海洋工程","水下","深海","港口",
                     "航海","水产","海工","深海装备"],
        "industry_kw": ["海洋","船舶","海工","水下"],
        "discipline_kw": ["海洋","船舶","海洋工程"],
    },
    "安全科学": {
        "keywords": ["安全","安防","消防","防护","保护","监控","监测","预警",
                     "应急","救援","安检","警用","反恐","防爆"],
        "industry_kw": ["安全","安防","消防","防护","监控"],
        "discipline_kw": ["安全","安防","消防"],
    },
    "核科学": {
        "keywords": ["核","核能","辐射","反应堆","放射","同位素","核燃料","核电",
                     "核物理","核医学","核检测"],
        "industry_kw": ["核","核电","核能","辐射"],
        "discipline_kw": ["核","核科学","核工程","物理"],
    },
    "量子科技": {
        "keywords": ["量子","量子计算","量子通信","量子加密","量子传感","量子芯片","量子比特",
                     "量子纠错","量子信息"],
        "industry_kw": ["量子","量子计算","量子通信"],
        "discipline_kw": ["量子","量子信息","物理"],
    },
    "仪器仪表": {
        "keywords": ["仪器","仪表","检测","测量","计量","测试","分析仪","光谱",
                     "色谱","质谱","精密仪器","传感器仪表","自动化仪表","实验设备"],
        "industry_kw": ["仪器","仪表","检测","测量","计量"],
        "discipline_kw": ["仪器","精密仪器","测量"],
    },
    "制造业": {
        "keywords": ["制造","加工","生产","装配","铸造","锻造","焊接","模具",
                     "装备","设备","机械","机床","阀门","泵","轴承","齿轮",
                     "钢结构","管道","电缆","电线"],
        "industry_kw": ["制造","装备","机械","模具","加工"],
        "discipline_kw": ["机械","制造","工程"],
    },
    "建筑工程": {
        "keywords": ["建筑","工程","施工","设计","建设","建材","混凝土","钢结构",
                     "装配式","地基","桥梁","隧道","市政","水利","水电"],
        "industry_kw": ["建筑","工程","施工","建设","水利"],
        "discipline_kw": ["建筑","土木","水利","工程"],
    },
}


def classify_supplier(supplier):
    """
    多维分类引擎 - 综合分析所有字段
    返回: (分类名称, 置信度评分)
    """
    name = (supplier.get("name") or "").lower()
    desc = (supplier.get("description") or "")[:200].lower()
    industry = (supplier.get("industry") or "").lower()
    discipline = (supplier.get("discipline") or "").lower()
    skills = " ".join(supplier.get("skills", []) or []).lower()

    results = []
    for cat, rules in CATEGORIES.items():
        score = 0

        # 1. 匹配名称 (weight 2)
        for kw in rules["keywords"]:
            if kw in name:
                score += 2

        # 2. 匹配描述 (weight 1)
        for kw in rules["keywords"]:
            if kw in desc:
                score += 1

        # 3. 匹配行业 (weight 3) - industry是DeepSeek提取的，较准确
        for kw in rules["industry_kw"]:
            if kw in industry:
                score += 3

        # 4. 匹配学科 (weight 3) - discipline也是DeepSeek提取的
        for kw in rules["discipline_kw"]:
            if kw in discipline:
                score += 3

        # 5. 匹配技能 (weight 2)
        for kw in rules["keywords"]:
            if kw in skills:
                score += 2

        # 6. 名称中分词匹配提升精度
        for word in name.split():
            word = word.strip("（）()有限公司股份集团")
            for kw in rules["keywords"]:
                if len(kw) >= 2 and kw == word:
                    score += 2

        if score > 0:
            results.append((cat, score))

    if not results:
        # 更细致的兜底分类
        if any(k in name for k in ["研究院","研究所","实验室","中心"]):
            return "科研机构", 1
        if any(k in name for k in ["公司","有限","股份","集团"]):
            return "其他", 0.5
        return "其他", 0

    # 按分数排序，取最高分
    results.sort(key=lambda x: -x[1])
    return results[0][0], results[0][1]


def fetch_all_suppliers():
    """获取所有供应商"""
    import requests as req
    all_items = []
    page = 1
    while True:
        try:
            r = req.get(f"{API_BASE}/api/suppliers?page={page}&per_page=200", timeout=15)
            data = r.json()
            items = data.get("items", [])
            if not items:
                break
            all_items.extend(items)
            total = data.get("total", 0)
            if len(all_items) >= total:
                break
            page += 1
        except Exception as e:
            print(f"  Fetch error: {e}")
            break
    return all_items


def update_category(supplier_id, category):
    """通过直接数据库更新 - 需要SSH"""
    # 这里记录需要更新的SQL，由外部执行
    return


def run(dry_run=False, target_category=None):
    import requests as req

    print("=" * 60)
    print("需求链 — 智能分类引擎 v1")
    print(f"模式: {'试跑(不修改)' if dry_run else '正式运行'}")
    print("=" * 60)

    # 1. 获取所有供应商
    print("\n[1/3] 获取供应商数据...")
    suppliers = fetch_all_suppliers()
    print(f"  共 {len(suppliers)} 个供应商")

    # 2. 分类
    print("\n[2/3] 执行智能分类...")
    changes = []
    current_cats = Counter()
    new_cats = Counter()

    for s in suppliers:
        old_cat = s.get("category") or "其他"
        current_cats[old_cat] += 1

        if target_category and old_cat != target_category:
            continue

        new_cat, confidence = classify_supplier(s)
        new_cats[new_cat] += 1

        if new_cat != old_cat and new_cat != "其他":
            changes.append({
                "id": s["id"],
                "name": s["name"],
                "old": old_cat,
                "new": new_cat,
                "confidence": confidence,
                "industry": s.get("industry",""),
                "discipline": s.get("discipline",""),
            })

    print(f"\n  分类变动: {len(changes)} 条需要更新")
    if changes:
        print(f"\n  变更多少 (前20条):")
        for c in changes[:20]:
            arrow = "🔄" if c["old"] != "其他" else "🆕"
            print(f"    {arrow} {c['name'][:40]:40s}  {c['old'][:12]:12s} → {c['new']} (conf={c['confidence']})")
        if len(changes) > 20:
            print(f"    ... 还有 {len(changes)-20} 条")

    # 分类分布对比
    print(f"\n  分类分布变化:")
    print(f"  {'分类':<20s} {'旧':>6s} {'新':>6s}")
    print(f"  {'-'*34}")
    all_cats = set(list(current_cats.keys()) + list(new_cats.keys()))
    for cat in sorted(all_cats):
        old = current_cats.get(cat, 0)
        new = new_cats.get(cat, 0)
        arrow = " ↑" if new > old else (" ↓" if new < old else "")
        print(f"  {cat:<20s} {old:>6d} {new:>6d}{arrow}")

    # 3. 更新数据库
    if not dry_run and changes:
        print("\n[3/3] 批量更新数据库...")
        sql_statements = []
        for c in changes:
            escaped_name = c["name"].replace("'", "''")
            sql_statements.append(
                f"UPDATE capability_profiles SET agent_card_json = jsonb_set(agent_card_json, '{{category}}', '\"{c['new']}\"') WHERE id = '{c['id']}';"
            )

        # 分批执行
        total = len(sql_statements)
        updated = 0
        for i in range(0, total, BATCH_SIZE):
            batch = sql_statements[i:i+BATCH_SIZE]
            sql = "BEGIN;\n" + "\n".join(batch) + "\nCOMMIT;"
            try:
                # 通过SSH执行SQL
                import subprocess, tempfile
                with tempfile.NamedTemporaryFile(mode="w", suffix=".sql", delete=False, encoding="utf-8") as f:
                    f.write(sql)
                    sql_file = f.name
                
                result = subprocess.run(
                    ["ssh", "-p", "2222", "root@demand-chain.duckdns.org",
                     f"docker exec -i dc-db psql -U dc -d demand_chain < {sql_file}"],
                    capture_output=True, text=True, timeout=30
                )
                updated += len(batch)
                print(f"  已更新 {updated}/{total} 条...")
            except Exception as e:
                print(f"  ❌ 更新出错: {e}")
            time.sleep(0.5)

        print(f"\n  ✅ 分类更新完成! 共更新 {updated} 条")

    print(f"\n{'=' * 60}")
    print(f"完成!")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    target = None
    for arg in sys.argv:
        if arg.startswith("--category="):
            target = arg.split("=", 1)[1]

    run(dry_run=dry, target_category=target)


