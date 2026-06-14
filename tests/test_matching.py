"""
匹配引擎单元测试 — 验证分类重叠度计算、候选排序、TF-IDF 索引构建。

不需要数据库连接即可运行（测试纯函数和对 TfidfSearch 的集成）。
"""
import pytest
from src.matching.engine import _category_overlap, match_one_demand
from src.shared.semantic_search import TfidfSearch


class TestCategoryOverlap:
    """_category_overlap 纯函数测试"""

    def test_exact_match(self):
        """相同分类返回 1.0"""
        assert _category_overlap("传感器技术", "传感器技术") == 1.0

    def test_case_insensitive(self):
        """大小写不敏感"""
        assert _category_overlap("Sensor", "sensor") == 1.0

    def test_substring(self):
        """包含关系返回 0.6"""
        assert _category_overlap("人工智能", "人工智能与机器学习") == 0.6
        assert _category_overlap("机器学习", "人工智能") == 0.0

    def test_no_match(self):
        """无关联返回 0.0"""
        assert _category_overlap("生物技术", "区块链") == 0.0

    def test_empty_input(self):
        """空值返回 0.0"""
        assert _category_overlap("", "传感器") == 0.0
        assert _category_overlap("传感器", "") == 0.0
        assert _category_overlap("", "") == 0.0
        assert _category_overlap(None, "传感器") == 0.0
        assert _category_overlap("传感器", None) == 0.0


class TestMatchOneDemand:
    """match_one_demand 集成测试（使用 TfidfSearch 进行文本匹配）"""

    @pytest.fixture
    def supplier_index(self):
        """构建一个包含 3 个供应商的 TF-IDF 索引"""
        idx = TfidfSearch()
        idx.add("p1", "高温传感器 800°C 管道检测 精度 ±0.5%")
        idx.add("p2", "低温等离子体 灭菌 医疗设备")
        idx.add("p3", "区块链 供应链 溯源 智能合约")
        idx.build_index()
        return idx

    @pytest.fixture
    def id_to_profile(self):
        """构建供应商 ID → 概要信息的映射"""
        from uuid import uuid4
        from unittest.mock import MagicMock

        profiles = {}
        for pid, name, cat in [
            ("p1", "高温传感器公司", "传感器技术"),
            ("p2", "医疗设备公司", "医疗设备"),
            ("p3", "区块链公司", "区块链"),
        ]:
            p = MagicMock()
            p.id = pid
            p.agent_card_json = {"name": name, "category": cat, "skills": []}
            p.trust_score = 0.5
            profiles[pid] = p
        return profiles

    @pytest.mark.asyncio
    async def test_match_high_temp_sensor(self, supplier_index, id_to_profile):
        """高温传感器需求应优先匹配高温传感器公司"""
        from uuid import uuid4
        from unittest.mock import MagicMock

        demand = MagicMock()
        demand.id = "d1"
        demand.raw_text = "需要一个800°C高温管道裂缝检测传感器，精度±0.5%"
        demand.structured_json = None
        demand.search_text = None
        demand.category = "传感器技术"

        results = await match_one_demand(demand, supplier_index, id_to_profile, top_k=3)
        assert len(results) > 0, "应返回匹配结果"
        assert results[0]["profile_id"] == "p1", "最高分应为高温传感器公司"
        assert results[0]["score"] > 0, "得分应大于 0"

    @pytest.mark.asyncio
    async def test_match_medical(self, supplier_index, id_to_profile):
        """医疗需求应优先匹配医疗设备公司"""
        from unittest.mock import MagicMock

        demand = MagicMock()
        demand.id = "d2"
        demand.raw_text = "需要一台低温等离子体灭菌设备"
        demand.structured_json = None
        demand.search_text = None
        demand.category = "医疗设备"

        results = await match_one_demand(demand, supplier_index, id_to_profile, top_k=3)
        assert len(results) > 0
        assert results[0]["profile_id"] == "p2"

    def test_dedup_by_name(self, supplier_index, id_to_profile):
        """测试同名供应商去重"""
        # 添加同名供应商（同名不同 ID）
        id_to_profile["p4"] = id_to_profile["p1"].__class__()  # clone
        id_to_profile["p4"].agent_card_json = {"name": "高温传感器公司", "category": "传感器技术", "skills": []}

        from unittest.mock import MagicMock
        demand = MagicMock()
        demand.id = "d3"
        demand.raw_text = "高温检测"
        demand.structured_json = None
        demand.search_text = None
        demand.category = "传感器技术"

        import asyncio
        results = asyncio.run(match_one_demand(demand, supplier_index, id_to_profile, top_k=3))
        names = [r["supplier_name"] for r in results]
        assert len(names) == len(set(names)), "同名供应商应去重"


class TestTfidfSearch:
    """TfidfSearch 单元测试"""

    def test_tokenize(self):
        from src.shared.semantic_search import tokenize
        tokens = tokenize("高温传感器 800°C")
        assert len(tokens) > 0, "应返回分词结果"
        assert "高温" in tokens or any("温" in t for t in tokens), "应包含中文 bigram"

    def test_search_roundtrip(self):
        idx = TfidfSearch()
        idx.add("d1", "高温传感器 管道检测 800°C")
        idx.add("d2", "区块链 供应链溯源")
        idx.build_index()

        results = idx.search("高温管道检测", top_k=5)
        best = results[0][0] if results else None
        assert best == "d1", "高温相关搜索应优先匹配 d1"

    def test_empty_query(self):
        idx = TfidfSearch()
        idx.add("d1", "一些文本")
        idx.build_index()
        results = idx.search("", top_k=5)
        assert len(results) == 1

    def test_no_documents(self):
        idx = TfidfSearch()
        idx.build_index()
        results = idx.search("anything", top_k=5)
        assert results == []
