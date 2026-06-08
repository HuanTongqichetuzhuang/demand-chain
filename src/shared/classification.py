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


CLASSIFY_PROMPT = """你是技术分类专家。根据需求文本，进行多维度分类标注。
严格使用以下分类体系，不要自创分类名称。

# 一级：科学学科（选最相关的1-3个，带3级层级）
可选顶级学科（共24个）：
- 数学（子：应用数学、计算数学、运筹学、统计学、概率论）
- 物理学（子：力学、热学、电磁学、光学、声学、量子力学、粒子物理、凝聚态物理、等离子体物理、天体物理）
- 化学（子：无机化学、有机化学、物理化学、分析化学、高分子化学、电化学）
- 生物学（子：分子生物学、细胞生物学、遗传学、微生物学、神经科学、生态学、生物信息学）
- 地球科学（子：地质学、气象学、海洋学、地球物理学、遥感）
- 天文学（子：天体测量、天体物理、宇宙学）
- 材料科学与工程（子：金属材料、无机非金属、高分子材料、复合材料、纳米材料、功能材料）
- 计算机科学与技术（子：人工智能、计算机视觉、自然语言处理、计算机网络、软件工程、数据库、安全）
- 电子科学与技术（子：微电子、光电子、电磁场与微波、集成电路、嵌入式系统）
- 信息与通信工程（子：通信系统、信号处理、无线通信、光纤通信）
- 机械工程（子：机械设计、制造工程、热能与动力工程、流体机械、振动控制）
- 电气工程（子：电力系统、电机与电器、高电压、电力电子）
- 土木工程（子：结构工程、岩土工程、桥梁工程、隧道工程）
- 化学工程（子：反应工程、分离工程、催化、过程控制）
- 环境科学与工程（子：水处理、大气治理、固废处理、环境监测、碳中和技术）
- 生物医学工程（子：医学影像、生物材料、康复工程、生物传感器）
- 航空航天科学与技术（子：飞行器设计、推进系统、导航制导、空间技术）
- 核科学与技术（子：核能、辐射防护、核医学、核探测）
- 农业科学（子：作物学、植物保护、畜牧学、水产、农业工程）
- 医学/药学（子：临床医学、药学、中药学、公共卫生、医学检验）
- 食品科学与工程（子：食品加工、食品安全、食品营养、发酵工程）
- 交通运输工程（子：道路工程、轨道交通、智能交通、物流工程）
- 仪器科学与技术（子：精密仪器、传感器技术、测试计量、分析仪器）
- 矿业工程（子：采矿工程、矿物加工、安全技术、油气开采）

# 二级：IPC国际专利分类（选最相关的1-5个大类）
IPC大类（完整版）：
A01 农业/林业；A21 焙烤；A22 屠宰/肉类加工；A23 食品/处理；A41 服装；A42 帽类；A43 鞋类；A45 手携物品；A46 刷类；A47 家具；A61 医学/兽医学/卫生学；A62 救生/消防；A63 运动/游戏/娱乐
B01 物理/化学方法；B02 破碎/粉碎；B03 分选；B05 喷涂/涂敷；B06 机械振动的发生；B07 固体的分离；B08 清洁；B09 固体废物处理；B21 金属加工；B22 铸造/粉末冶金；B23 机床/焊接；B24 磨削/抛光；B25 手动工具；B26 切割；B27 木材加工；B28 水泥/陶瓷加工；B29 塑料加工；B30 压力机；B31 纸品加工；B32 层状产品；B60 一般车辆；B62 无轨车辆；B63 船舶；B64 航空；B65 输送/包装/贮存；B66 卷扬/提升/牵引；B67 液体的贮运；B68 鞍具/家具装饰；B81 微观结构技术；B82 纳米技术
C01 无机化学；C02 水处理；C03 玻璃/矿棉；C04 水泥/陶瓷；C05 肥料；C06 炸药/火柴；C07 有机化学；C08 高分子化合物；C09 染料/涂料/抛光剂；C10 石油/燃气；C11 动植物油；C12 生物化学/遗传工程；C13 制糖/淀粉；C14 皮革处理；C21 铁的冶金；C22 冶金/合金；C23 金属表面处理；C25 电解/电泳；C30 晶体生长
D01 纺织/纤维；D02 纱线；D03 织造；D04 编带/花边；D05 缝纫/绣花；D06 织物处理；D07 绳/缆；D21 造纸
E01 道路/铁路/桥梁；E02 水利工程；E03 给排水；E04 建筑物；E05 锁/钥匙；E06 门窗；E21 采矿
F01 机器/发动机；F02 燃烧发动机；F03 液力机械；F04 泵/压缩机；F15 流体执行机构；F16 工程元件（轴承、密封、阀门、管接头）；F17 气体贮运；F21 照明；F22 蒸汽发生；F23 燃烧设备；F24 供热/通风；F25 制冷/干燥；F26 干燥；F27 炉/窑；F28 热交换
G01 测量/测试（传感器、计量、分析仪器）；G02 光学（透镜、光纤、显示）；G03 摄影/全息；G04 测时；G05 控制/调节；G06 计算/推算（AI、算法）；G07 核算装置；G08 信号装置；G09 教育/密码术；G10 乐器/声学；G11 信息存储；G12 仪器的零部件；G16 特别适用于特定领域的ICT
H01 基本电气元件（电阻、电容、半导体、天线）；H02 发电/变电/配电；H03 基本电子电路；H04 电通信技术（5G、WiFi、蓝牙、光纤通信）；H05 其他电技术（印刷电路、X射线、等离子体）；H10 半导体器件

# 三级：制造工艺/方法
可选：
- 材料制备（铸造、锻造、粉末冶金、3D打印/增材制造、CVD、PVD、溶胶-凝胶法、静电纺丝）
- 机械加工（车削、铣削、磨削、钻孔、电火花加工EDM、激光加工、超声波加工、水刀切割）
- 热处理（退火、淬火、回火、正火、渗碳、渗氮、感应加热）
- 表面处理（电镀、阳极氧化、喷涂、喷砂、PVD镀膜、钝化、酸洗）
- 焊接与连接（电弧焊、激光焊、超声波焊、冷焊、扩散焊、胶接、铆接）
- 半导体工艺（光刻、刻蚀、离子注入、外延生长、CMP、ALD原子层沉积、封装）
- 生物工艺（发酵、细胞培养、PCR、基因测序、CRISPR编辑、蛋白质纯化、冷冻干燥）
- 化学工艺（蒸馏、萃取、催化、结晶、聚合、色谱分离、膜分离）
- 检测与分析（光谱、色谱、质谱、XRD、SEM、TEM、AFM原子力显微镜、核磁共振NMR）
- 软件方法（机器学习、深度学习、强化学习、CV、NLP、大语言模型、联邦学习、知识图谱）
- 能源技术（光伏、风电、储能/电池、氢能、核能、燃料电池、超导）
- 环保工艺（污水处理、废气治理、固废处理、碳捕集CCUS、土壤修复）

# 四：技术成熟度（TRL）
- TRL 1-2：基础研究/概念验证
- TRL 3-4：实验室验证
- TRL 5-6：原型/模拟环境验证
- TRL 7-8：实际环境验证/小批量
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
