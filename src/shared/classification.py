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


CLASSIFY_PROMPT = """你是技术与需求分类专家。根据需求文本，进行多维度分类标注。
严格使用以下分类体系，不要自创分类名称。分类越精细，匹配效率越高。

# 一、科学学科（35个顶级学科 × 3级层级）

## 自然科学（理学）
1. 数学 — 应用数学、计算数学、运筹学、统计学、概率论、数论、几何学、拓扑学
2. 物理学 — 力学、热学、电磁学、光学、声学、量子力学、粒子物理、凝聚态物理、等离子体物理、天体物理、原子分子物理、非线性物理
3. 化学 — 无机化学、有机化学、物理化学、分析化学、高分子化学、电化学、配位化学、量子化学
4. 生物学 — 分子生物学、细胞生物学、遗传学、微生物学、神经科学、生态学、生物信息学、免疫学、发育生物学、合成生物学
5. 地球科学 — 地质学、气象学、海洋学、地球物理学、遥感、地理信息系统GIS、水文地质、地震学
6. 天文学 — 天体测量、天体物理、宇宙学、射电天文学、行星科学

## 工程与技术
7. 材料科学与工程 — 金属材料、无机非金属、高分子材料、复合材料、纳米材料、功能材料、智能材料、生物材料、超导材料
8. 计算机科学与技术 — 人工智能、计算机视觉、NLP、计算机网络、软件工程、数据库、信息安全、分布式系统、操作系统、编译原理
9. 电子科学与技术 — 微电子、光电子、电磁场与微波、集成电路IC设计、嵌入式系统、MEMS微机电系统
10. 信息与通信工程 — 通信系统、信号处理、无线通信5G/6G、光纤通信、卫星通信、物联网IoT
11. 控制科学与工程 — 自动控制、机器人学、智能系统、多智能体系统、无人机控制
12. 机械工程 — 机械设计、制造工程、热能与动力工程、流体机械、振动控制、精密加工、摩擦学
13. 电气工程 — 电力系统、电机与电器、高电压技术、电力电子、智能电网
14. 土木工程 — 结构工程、岩土工程、桥梁工程、隧道工程、抗震工程、工程管理
15. 建筑学 — 建筑设计、城市规划、景观设计、建筑物理、建筑历史与理论
16. 化学工程 — 反应工程、分离工程、催化、过程控制、化工安全、精细化工
17. 环境科学与工程 — 水处理、大气治理、固废处理、环境监测、碳中和技术、土壤修复、噪声控制
18. 生物医学工程 — 医学影像、生物材料、康复工程、生物传感器、组织工程、脑机接口BCI
19. 航空航天科学与技术 — 飞行器设计、推进系统、导航制导、空间技术、空气动力学、卫星技术
20. 核科学与技术 — 核能、辐射防护、核医学、核探测、核聚变、同位素技术
21. 仪器科学与技术 — 精密仪器、传感器技术、测试计量、分析仪器、智能仪器
22. 测绘科学与技术 — 卫星导航GNSS、三维激光扫描、摄影测量、地图制图
23. 矿业工程 — 采矿工程、矿物加工、安全技术、油气开采、矿山机械
24. 冶金工程 — 钢铁冶金、有色金属冶金、粉末冶金、电冶金
25. 纺织科学与工程 — 纺织工程、服装设计、纤维材料、印染技术
26. 轻工技术与工程 — 制浆造纸、皮革化学、日用化工、包装工程
27. 食品科学与工程 — 食品加工、食品安全、食品营养、发酵工程、酿造技术
28. 交通运输工程 — 道路工程、轨道交通、智能交通ITS、物流工程、自动驾驶、航海技术
29. 船舶与海洋工程 — 船舶设计、海洋平台、水下机器人、海洋能源
30. 水利工程 — 水资源管理、水工结构、防洪工程、水力发电
31. 安全科学与工程 — 生产安全、消防工程、应急管理、爆炸防护

## 生命与医学
32. 医学/药学 — 临床医学、药学、中药学、公共卫生、医学检验、精准医疗、基因治疗
33. 农业科学 — 作物学、植物保护、畜牧学、水产养殖、农业工程、智慧农业、土壤学

## 人文与社科
34. 经济学/管理学 — 创新管理、技术经济、产业组织、运筹管理、供应链管理、知识产权管理
35. 教育学 — 教育技术、教育心理学、课程设计、在线教育、职业教育

# 二、应用行业（40个行业大类）
选最相关的1-3个。
A 农/林/牧/渔业 — 种植业、畜牧业、渔业、林业
B 采矿业 — 煤炭、石油天然气、金属矿、非金属矿
C 制造业 — 食品制造、纺织服装、化工、医药制造、金属加工、汽车、电子、机械、航空航天、新能源装备
D 电力/能源 — 火力发电、水力发电、核能、光伏、风电、储能、氢能
E 建筑业 — 房屋建筑、市政工程、交通基建、装饰装修
F 交通运输/物流 — 铁路、公路、水运、航空、仓储物流、快递
G 信息传输/软件 — 电信、互联网、软件开发、云计算、大数据、AI服务
H 金融业 — 银行、证券、保险、风险投资、金融科技
I 房地产业
J 科学研究/技术服务 — 自然科学、工程技术、检验检测、技术推广、知识产权服务
K 环保/水利 — 环境治理、资源回收、水利管理
L 教育 — 基础教育、高等教育、职业培训、在线教育
M 医疗/卫生 — 医院、公共卫生、养老、康复
N 文化/体育/娱乐 — 影视、游戏、出版、体育、旅游
O 公共管理/国防 — 政府、消防、国防军工
P 碳中和/气候科技
Q 智慧城市
R 元宇宙/Web3/区块链

# 三、IPC国际专利分类（80+大类，选最相关的1-5个）
A01农业 A21焙烤 A22屠宰 A23食品 A41服装 A47家具 A61医学 A62消防 A63运动
B01物理化学方法 B02破碎 B03分选 B05喷涂 B08清洁 B21金属加工 B22铸造粉末冶金 B23机床焊接 B24磨削 B25手动工具 B26切割 B28水泥 B29塑料 B32层状 B60车辆 B63船舶 B64航空 B65包装 B81微结构 B82纳米
C01无机化学 C02水处理 C03玻璃 C04水泥 C05肥料 C06炸药 C07有机化学 C08高分子 C09染料涂料 C10石油 C11动植物油 C12生物化学遗传工程 C21铁冶金 C22合金 C23表面处理 C25电镀 C30晶体生长
D01纺织 D02纱线 D03织造 D05缝纫 D06处理 D07绳缆 D21造纸
E01道路桥梁 E02水利 E03给排水 E04建筑 E05锁 E06门窗 E21采矿
F01发动机 F02内燃机 F03液压 F04泵压缩机 F16轴承密封阀门 F21照明 F23燃烧 F24供热 F25制冷 F27炉 F28热交换
G01测量传感器 G02光纤光学 G03摄影全息 G05控制 G06计算AI算法 G08信号 G09教育 G10声学 G11存储 G16领域ICT
H01电阻电容半导体天线 H02发电配电 H03电路 H04通信5GWiFi蓝牙 H05印刷电路X射线等离子体 H10半导体器件

# 四、制造工艺/方法（14大类 × 120+方法）
- 材料制备（铸造、锻造、粉末冶金、3D打印/增材制造、CVD、PVD、溶胶-凝胶法、静电纺丝、激光熔覆、等离子喷涂、热压烧结）
- 机械加工（车削、铣削、磨削、钻孔、电火花加工EDM、激光加工、超声波加工、水刀切割、微加工、纳米加工）
- 热处理（退火、淬火、回火、正火、渗碳、渗氮、感应加热、真空热处理）
- 表面处理（电镀、阳极氧化、喷涂、喷砂、PVD镀膜、钝化、酸洗、等离子渗氮）
- 焊接与连接（电弧焊、激光焊、超声波焊、冷焊、扩散焊、胶接、铆接、搅拌摩擦焊）
- 半导体工艺（光刻、刻蚀、离子注入、外延生长、CMP、ALD原子层沉积、封装、晶圆键合、EBL电子束光刻）
- 生物工艺（发酵、细胞培养、PCR、基因测序、CRISPR编辑、蛋白质纯化、冷冻干燥、单细胞分析）
- 化学工艺（蒸馏、萃取、催化、结晶、聚合、色谱分离、膜分离、微波合成、光催化）
- 检测与分析（光谱、色谱、质谱、XRD、SEM、TEM、AFM原子力显微镜、核磁共振NMR、X射线CT、拉曼光谱）
- 软件方法（机器学习、深度学习、强化学习、CV、NLP、大语言模型、联邦学习、知识图谱、量子计算模拟、数字孪生）
- 能源技术（光伏、风电、储能/电池、氢能、核能、燃料电池、超导、光热发电、地热能）
- 环保工艺（污水处理、废气治理、固废处理、碳捕集CCUS、土壤修复、噪声治理、VOCs治理）
- 通信与网络（5G NR、WiFi7、蓝牙LE、LoRa、NB-IoT、卫星互联网、量子通信、光通信DWDM）
- 前沿交叉（量子计算、脑机接口BCI、DNA存储、光遗传学、类脑计算、柔性电子）

# 五、技术成熟度（TRL）
- TRL 1-2：基础研究/概念验证
- TRL 3-4：实验室验证
- TRL 5-6：原型/模拟环境验证
- TRL 7-8：实际环境验证/小批量
- TRL 9：量产成熟

# 六、需求来源（选1个）
- 个人研究者/独立发明家
- 高校/实验室
- 企业研发部门
- 政府/国防
- 初创公司
- 行业协会
- 非盈利机构
- 其他

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
