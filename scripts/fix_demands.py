#!/usr/bin/env python3
"""
需求链平台 — 需求分类&标签引擎
为现有需求生成精确分类和标签，补全 structured_json
"""
import json, subprocess, urllib.request

API = "http://localhost:8080/api/demands?limit=200"

# 需求分类规则 - 根据raw_text关键词
DEMAND_CATEGORIES = {
    "人工智能": ["ai","人工智能","机器学习","深度学习","大模型","llm","nlp","计算机视觉","自然语言","神经网络","智能算法"],
    "生物医药": ["生物医药","制药","药物","临床","基因","疫苗","抗体","医疗","健康","诊断","癌症","肿瘤","疾病","生物医学","细胞","蛋白","糖尿病","心血管","病毒","抗生素"],
    "新能源": ["新能源","光伏","风电","氢能","储能","电池","太阳能","锂电","钙钛矿","燃料电池","能源","清洁能源","可再生能源","电网调峰","绿氢"],
    "环境工程": ["环境","环保","水处理","废水","大气","固废","碳捕集","碳中和","减排","节能","回收","再生","绿色","气候","生态","海水淡化","污染","野火","消防"],
    "材料科学": ["材料","高分子","复合","纳米","涂层","合金","陶瓷","石墨烯","碳纤维","自愈合","可降解","塑料","弹性体","聚合物","电解质"],
    "航空航天": ["航天","航空","卫星","无人机","火箭","推进","发动机","飞控","航电","空间站","太空","低轨","星座","航天器"],
    "机器人与智能系统": ["机器人","自动化","slam","无人系统","机械臂","agv","无人车","自主导航","缺陷检测","视觉检测","移动机器人"],
    "信息技术": ["量子","区块链","网络安全","软件","平台","数据","加密","隐私计算","联邦学习","共识算法","信息安全","数字化"],
    "传感器技术": ["传感器","mems","检测","传感","触觉","陀螺","惯性","雷达","lidar"],
    "交通运输": ["交通","物流","汽车","电动车","自动驾驶","智能驾驶","轨道","车辆","地面车","船舶"],
    "农业科学": ["农业","作物","养殖","食品","农药","化肥","农机","畜牧","水产","植物工厂"],
    "海洋科学": ["海洋","海水","水下","深海","船舶","海工"],
}

# 按类别提取标签词
TAG_RULES = {
    "人工智能": ["AI","机器学习","深度学习","大模型","NLP","计算机视觉","联邦学习","隐私计算"],
    "生物医药": ["基因编辑","CRISPR","诊断","疫苗","药物研发","临床","细胞治疗","生物传感器","血糖监测"],
    "新能源": ["光伏","锂电","氢能","储能","钙钛矿","可再生","清洁能源"],
    "环境工程": ["碳捕集","水处理","海水淡化","碳中和","野火","可持续","回收","节能"],
    "材料科学": ["自愈合材料","高分子","纳米","复合材料","碳纤维","3D打印","固态电解质"],
    "航空航天": ["卫星","无人机","推进系统","航天器","低轨星座","火箭"],
    "机器人与智能系统": ["SLAM","自主导航","缺陷检测","视觉检测","工业机器人","移动机器人"],
    "信息技术": ["量子计算","区块链","隐私计算","联邦学习","共识算法"],
    "传感器技术": ["MEMS","触觉传感器","惯性传感器","雷达","LiDAR"],
    "交通运输": ["自动驾驶","智能驾驶","地面车辆","物流"],
    "农业科学": ["农业无人机","农业机器人","植物工厂"],
    "海洋科学": ["深海","水下","船舶"],
}


def classify_and_tag(text, category=""):
    """根据需求文本推断分类和标签"""
    text_lower = text.lower()

    # 分类评分
    scores = {}
    for cat, kws in DEMAND_CATEGORIES.items():
        score = sum(2 for kw in kws if kw in text_lower)
        if score > 0:
            scores[cat] = score

    best_cat = max(scores, key=scores.get) if scores else (category or "其他")

    # 提取标签
    tags = []
    for cat, tag_list in TAG_RULES.items():
        if cat == best_cat:
            for tag in tag_list:
                if tag.lower() in text_lower:
                    tags.append(tag)

    # 从内容中提取数字指标作为额外标签
    if "万" in text or "$" in text:
        import re
        amounts = re.findall(r'[\$]?[\d,]+[万亿]?', text)
        for a in amounts[:2]:
            tags.append(f"奖金{a.strip()}")
    
    # 去重并限制数量
    tags = list(dict.fromkeys(tags))[:5]
    if not tags:
        tags = [best_cat]

    return best_cat, tags


def run():
    # 获取所有需求
    r = urllib.request.urlopen(API, timeout=15)
    demands = json.loads(r.read())
    print(f"共 {len(demands)} 条需求")

    sql_updates = []
    for d in demands:
        raw = d.get("raw_text", "")
        old_cat = d.get("category", "其他")
        current_summary = d.get("summary", "")
        current_tags = d.get("tags", [])

        new_cat, new_tags = classify_and_tag(raw, old_cat)
        
        # 构建structured_json
        summary = current_summary or raw[:100] + ("..." if len(raw) > 100 else "")
        if not new_tags:
            new_tags = current_tags
        
        sj = {
            "summary": summary,
            "tags": new_tags,
        }
        sj_json = json.dumps(sj, ensure_ascii=False)

        did = d["id"]
        sql_updates.append(
            f"UPDATE demands SET category = '{new_cat}', "
            f"structured_json = '{sj_json}'::jsonb, "
            f"search_text = '{' '.join(new_tags)}' "
            f"WHERE id = '{did}';"
        )

        if new_cat != old_cat or len(new_tags) > len(current_tags):
            print(f"  {'🔄' if new_cat != old_cat else '🏷️'} {raw[:50]}...  {old_cat}→{new_cat} tags:{len(current_tags)}→{len(new_tags)}")

    print(f"\n需要更新: {len(sql_updates)} 条")

    # 批量执行
    batch_size = 50
    for i in range(0, len(sql_updates), batch_size):
        batch = sql_updates[i:i+batch_size]
        sql = "BEGIN;\n" + "\n".join(batch) + "\nCOMMIT;"
        proc = subprocess.run(
            ["docker", "exec", "-i", "dc-db", "psql", "-U", "dc", "-d", "demand_chain"],
            input=sql.encode(), capture_output=True, timeout=30)
        done = min(i+batch_size, len(sql_updates))
        print(f"  已更新 {done}/{len(sql_updates)}")
        if proc.returncode != 0:
            print(f"  ❌ {proc.stderr.decode()[:100]}")

    print(f"\n✅ 完成!")

    # 验证
    proc2 = subprocess.run(
        ["docker", "exec", "-i", "dc-db", "psql", "-U", "dc", "-d", "demand_chain",
         "-c", "SELECT category, COUNT(*) FROM demands GROUP BY category ORDER BY COUNT(*) DESC;"],
        capture_output=True, timeout=10)
    print(proc2.stdout.decode())


if __name__ == "__main__":
    run()
