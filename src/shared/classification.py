"""
需求分类引擎 — 多维度学科/技术/工艺标注体系。

基于标准分类法（IPC、FOS、国标），使用 LLM 将每条需求映射到：
1. 科学学科（3级层级）
2. 工程技术领域（IPC分类）
3. 制造工艺/方法
4. 应用行业
"""
import json
import logging
from dataclasses import dataclass, field
from typing import Optional

from src.adapters.llm_client import get_llm

logger = logging.getLogger(__name__)


CLASSIFY_PROMPT = """你是技术分类专家。根据需求文本和已有的结构化信息，进行多维度分类标注。
严格使用以下分类体系，不要自创分类名称。

# 一级：科学学科（选最相关的1-3个，带3级层级）
可选顶级学科：
- 数学
- 物理学（子：力学、热学、电磁学、光学、量子力学、相对论与引力物理、凝聚态物理、等离子体物理）
- 化学（子：无机化学、有机化学、物理化学、分析化学、高分子化学）
- 生物学（子：分子生物学、细胞生物学、遗传学、微生物学、神经科学）
- 地球科学（子：地质学、气象学、海洋学）
- 材料科学与工程
- 计算机科学与技术（子：人工智能、计算机视觉、自然语言处理、计算机网络、软件工程）
- 电子科学与技术（子：微电子、光电子、电磁场与微波）
- 机械工程（子：机械设计、制造工程、热能与动力工程）
- 电气工程
- 土木工程
- 化学工程
- 环境科学与工程
- 生物医学工程
- 航空航天科学与技术
- 核科学与技术

# 二级：IPC国际专利分类（选最相关的1-5个大类）
IPC大类（部分）：
A01 农业；A61 医学/卫生学
B01 物理/化学方法；B23 机床；B29 塑料加工；B65 输送/包装
C01 无机化学；C07 有机化学；C08 高分子化合物；C12 生物化学
D01 纺织
E02 水利工程；E04 建筑物
F16 工程元件；F24 供热；F25 制冷
G01 测量/测试；G02 光学；G05 控制/调节；G06 计算/推算；G08 信号装置；G09 教育
H01 基本电气元件；H02 发电/变电；H04 电通信技术；H05 其他电技术

# 三级：制造工艺/方法
可选：
- 材料制备（铸造、锻造、粉末冶金、3D打印/增材制造、化学气相沉积CVD、物理气相沉积PVD、溶胶-凝胶法）
- 机械加工（车削、铣削、磨削、电火花加工EDM、激光加工、超声波加工）
- 热处理（退火、淬火、回火、渗碳、渗氮）
- 表面处理（电镀、阳极氧化、喷涂、喷砂）
- 焊接与连接（电弧焊、激光焊、超声波焊、冷焊、胶接）
- 半导体工艺（光刻、刻蚀、离子注入、外延生长、CMP）
- 生物工艺（发酵、细胞培养、PCR、基因测序、CRISPR编辑）
- 化学工艺（蒸馏、萃取、催化、结晶、聚合）
- 检测与分析（光谱分析、色谱分析、质谱分析、X射线衍射XRD、扫描电镜SEM、透射电镜TEM）
- 软件方法（机器学习、深度学习、强化学习、计算机视觉、NLP）

# 四：技术成熟度（TRL）
- TRL 1-2：基础研究
- TRL 3-4：实验室验证
- TRL 5-6：原型/模拟环境验证
- TRL 7-8：实际环境验证
- TRL 9：量产成熟

# 输出JSON格式
{
  "disciplines": [
    {"name": "物理学", "sub": "电磁学", "sub_sub": "", "relevance": 0.9}
  ],
  "ipc_classes": [
    {"code": "G01", "name": "测量/测试", "relevance": 0.85}
  ],
  "processes": [
    {"name": "化学气相沉积CVD", "category": "材料制备", "relevance": 0.7}
  ],
  "trl": {"level": 4, "label": "实验室验证"},
  "analysis": "50字以内的分类理由"
}"""


@dataclass
class ClassificationResult:
    """多维度分类结果"""
    disciplines: list[dict] = field(default_factory=list)
    ipc_classes: list[dict] = field(default_factory=list)
    processes: list[dict] = field(default_factory=list)
    trl: dict = field(default_factory=lambda: {"level": 0, "label": "未知"})
    analysis: str = ""

    def to_dict(self) -> dict:
        return {
            "disciplines": self.disciplines,
            "ipc_classes": self.ipc_classes,
            "processes": self.processes,
            "trl": self.trl,
            "analysis": self.analysis,
        }

    def to_search_text(self) -> str:
        """生成可搜索的文本摘要"""
        parts = []
        for d in self.disciplines:
            parts.append(f"{d.get('name','')}/{d.get('sub','')}/{d.get('sub_sub','')}")
        for i in self.ipc_classes:
            parts.append(f"IPC:{i.get('code','')} {i.get('name','')}")
        for p in self.processes:
            parts.append(f"{p.get('category','')}→{p.get('name','')}")
        return " | ".join(parts)

    def to_discipline_path(self) -> list[str]:
        """返回学科路径列表，用于分类树导航"""
        paths = []
        for d in self.disciplines:
            path = "/".join(filter(None, [d.get("name",""), d.get("sub",""), d.get("sub_sub","")]))
            paths.append(path)
        return paths


class ClassificationService:
    """需求分类服务"""

    def __init__(self):
        self.llm = get_llm()

    async def classify(self, raw_text: str, structured: dict = None) -> ClassificationResult:
        """对一条需求进行多维度分类"""
        context = raw_text
        if structured:
            context = json.dumps(structured, ensure_ascii=False)

        try:
            response = await self.llm.chat(CLASSIFY_PROMPT, context)
            data = json.loads(response)

            return ClassificationResult(
                disciplines=data.get("disciplines", []),
                ipc_classes=data.get("ipc_classes", []),
                processes=data.get("processes", []),
                trl=data.get("trl", {"level": 0, "label": "未知"}),
                analysis=data.get("analysis", ""),
            )
        except Exception as e:
            logger.error(f"分类失败: {e}")
            return ClassificationResult(analysis=f"分类失败: {e}")

    @staticmethod
    def to_index_fields(result: ClassificationResult) -> dict:
        """转为数据库可存储的字段"""
        return {
            "classification": result.to_dict(),
            "search_text": result.to_search_text(),
            "discipline_path": result.to_discipline_path(),
            "ipc_codes": [i["code"] for i in result.ipc_classes],
            "process_categories": list(set(p["category"] for p in result.processes)),
        }


classification_service = ClassificationService()
