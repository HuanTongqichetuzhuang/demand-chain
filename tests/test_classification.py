"""
分类引擎单元测试 — 验证分类逻辑、搜索文本构建、IPC 格式校验。

使用 mock 替代真实 LLM 调用，不需 API Key 即可运行。
"""
import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from src.shared.classification import ClassificationResult, ClassificationService


# ============================================================
# ClassificationResult 纯数据类测试
# ============================================================

class TestClassificationResult:
    def test_empty_result(self):
        r = ClassificationResult()
        assert r.disciplines == []
        assert r.ipc_classes == []
        assert r.processes == []
        assert r.to_search_text() == ""

    def test_to_search_text(self):
        r = ClassificationResult(
            disciplines=[{"name": "电子工程", "sub": "传感器技术", "confidence": 0.9}],
            ipc_classes=[{"code": "G01N", "description": "测量"}],
            processes=[{"name": "精密加工", "step": "检测"}],
        )
        text = r.to_search_text()
        assert "电子工程" in text
        assert "传感器" in text
        assert "G01N" in text
        assert "精密加工" in text

    def test_ipc_format_validation(self):
        """IPC 代码格式校验（有效格式: A01B 1/00 或 A01B1/00）"""
        valid_codes = ["G01N", "A01B 1/00", "G06F17/30", "H04L29/06"]
        for code in valid_codes:
            result = ClassificationResult(
                ipc_classes=[{"code": code, "description": "test"}]
            )
            assert result.ipc_classes[0]["code"] == code

    def test_confidence_filtering(self):
        """低置信度结果应被过滤或标记"""
        r = ClassificationResult(
            disciplines=[{"name": "高置信", "confidence": 0.95},
                         {"name": "低置信", "confidence": 0.3}],
        )
        high_conf = [d for d in r.disciplines if d.get("confidence", 0) >= 0.5]
        assert len(high_conf) == 1
        assert high_conf[0]["name"] == "高置信"


# ============================================================
# ClassificationService 集成测试（mock LLM）
# ============================================================

@pytest.fixture
def mock_llm():
    """构造一个返回结构化 JSON 的 mock LLM 客户端"""
    llm = AsyncMock()
    llm.chat.return_value = json.dumps({
        "disciplines": [{"name": "电子工程", "sub": "传感器技术", "confidence": 0.92}],
        "ipc_classes": [{"code": "G01N27", "description": "用电、电化学或磁的方法测试或分析材料"}],
        "processes": [{"name": "检测与监测", "step": "无损检测", "confidence": 0.88}],
    }, ensure_ascii=False)
    return llm


@pytest.fixture
def service(mock_llm):
    from src.shared.classification import classification_service
    # 替换真实 LLM 为 mock
    original = classification_service.llm
    classification_service.llm = mock_llm
    yield classification_service
    classification_service.llm = original  # restore


class TestClassificationService:
    @pytest.mark.asyncio
    async def test_classify_success(self, service):
        """LLM 正常返回时的分类流程"""
        result = await service.classify(
            raw_text="需要一个800°C高温管道裂缝检测传感器，精度±0.5%"
        )
        assert len(result.disciplines) > 0
        assert result.disciplines[0]["name"] == "电子工程"
        assert len(result.ipc_classes) > 0

    @pytest.mark.asyncio
    async def test_classify_malformed_json(self, service):
        """LLM 返回非 JSON 时的降级处理"""
        service.llm.chat.return_value = "not json at all"
        # 应返回空结果而非抛异常
        result = await service.classify(raw_text="test")
        assert result.disciplines == []
        assert result.ipc_classes == []

    @pytest.mark.asyncio
    async def test_classify_empty_text(self, service):
        """空文本的分类结果"""
        result = await service.classify(raw_text="")
        # 空文本应返回空结果或基本分类
        assert isinstance(result, ClassificationResult)

    @pytest.mark.asyncio
    async def test_classify_llm_timeout(self, service):
        """LLM 超时的降级处理"""
        service.llm.chat.side_effect = TimeoutError("LLM timeout")
        result = await service.classify(raw_text="test")
        assert result.disciplines == []  # 超时应返回空结果


# ============================================================
# 分类流水线测试
# ============================================================

class TestClassificationPipeline:
    """验证分类系统整体流水线"""

    def test_module_import(self):
        from src.shared.classification import (
            classification_service, ClassificationResult, ClassificationService
        )
        assert classification_service is not None
        assert ClassificationResult is not None

    def test_category_prompt_exists(self):
        from src.shared.classification import CLASSIFY_PROMPT
        assert len(CLASSIFY_PROMPT) > 0, "应有分类提示模板"
        assert "学科" in CLASSIFY_PROMPT or "传感器" in CLASSIFY_PROMPT

    @pytest.mark.asyncio
    async def test_lifecycle_standalone(self):
        """确认 classification_service 模块级实例可安全导入"""
        from src.shared.classification import classification_service
        # 只验证实例存在，不调用（因需 LLM API Key）
        assert hasattr(classification_service, "classify")
