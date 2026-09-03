# -*- coding: utf-8 -*-
"""
build_inventory.py  —— 低空经济无人机法律知识库 · 法规清单表生成器
自动产出：
  法规清单总表.csv   (UTF-8-BOM, Excel 可直接打开)
  法规清单总表.md    (人类可读, 按效力层级分节)
并对 law/ 目录做覆盖率自检（有文件却未登记 / 已登记却缺文件 → 打印告警）。
数据来源：本文件内 RECORDS(人工核校) + 06/07 目录 JSON + raw/pkulaw chunk 库。
"""
import csv, json, os, sys, glob, re
sys.stdout.reconfigure(encoding="utf-8")
KB = os.path.dirname(os.path.abspath(__file__))
def rel(p): return os.path.relpath(p, KB).replace("\\", "/")

# ---- 已入库法规名（用于标注 是否已切分入库） ----
ingested_names = set()
for f in ["raw/chunks_all.json", "pkulaw/out/chunks_pkulaw.json"]:
    try:
        for ch in json.load(open(os.path.join(KB, f), encoding="utf-8")):
            m = ch.get("metadata", ch)
            n = m.get("法规名") or m.get("法规名称")
            if n: ingested_names.add(n.strip())
    except Exception as e:
        print("WARN load", f, e)

# ============================================================
# 主数据：每条 = 一部法规/规范性文件/标准。字段与 RAG chunk 元数据对齐。
# ingested: 是/部分/否   path: 相对 knowledge_base 路径（"" = 尚未本地存档）
# ============================================================
R = []
def add(**k): R.append(k)

# ---------- ① 法律（全国人大及常委会） ----------
G = "法律"
add(cat=G, title="中华人民共和国民用航空法", organ="全国人大常委会",
    docno="主席令第44号(2025修订)", pub="2025-12-27", eff="2026-07-01", status="现行有效(2026版)",
    scope="民用航空全领域；2026版首次纳入无人驾驶航空器/低空经济专门条款(第34条适航许可、第61条机场管制空域等)",
    path="law/01_法律/中华人民共和国民用航空法.html",
    url="https://www.caac.gov.cn/", ingested="是", note="★核心上位法；须用2026-07-01新版，非2021修正版")
add(cat=G, title="中华人民共和国刑法", organ="全国人大及常委会",
    docno="主席令(1997修订，含修正案十二)", pub="1997-03-14", eff="1997-10-01", status="现行有效",
    scope="黑飞危害公共安全、非法测绘、非法获取国家秘密、扰乱单位秩序等的刑事责任",
    path="law/01_法律/中华人民共和国刑法.pdf", url="https://www.gov.cn/", ingested="否",
    note="按相关罪名条款抽取即可，无需全文入库")
add(cat=G, title="中华人民共和国治安管理处罚法", organ="全国人大常委会",
    docno="主席令(2025修订)", pub="2025-06-27", eff="2026-01-01", status="现行有效(2026版)",
    scope="违规飞行/黑飞扰序、扰乱公共场所秩序、妨害公共安全的行政处罚",
    path="law/01_法律/中华人民共和国治安管理处罚法.html", url="https://www.gov.cn/", ingested="否",
    note="2026-01-01施行新版；无人机黑飞常用行政处罚依据")
add(cat=G, title="中华人民共和国个人信息保护法", organ="全国人大常委会",
    docno="主席令第91号", pub="2021-08-20", eff="2021-11-01", status="现行有效",
    scope="无人机航拍/巡检采集人脸、车牌等个人信息的合规",
    path="law/01_法律/中华人民共和国个人信息保护法.html", url="https://www.gov.cn/", ingested="否")
add(cat=G, title="中华人民共和国数据安全法", organ="全国人大常委会",
    docno="主席令第84号", pub="2021-06-10", eff="2021-09-01", status="现行有效",
    scope="无人机采集/传输测绘、遥感等数据的安全管理",
    path="law/01_法律/中华人民共和国数据安全法.html", url="https://www.gov.cn/", ingested="否")
add(cat=G, title="中华人民共和国网络安全法", organ="全国人大常委会",
    docno="主席令第53号(2016)", pub="2016-11-07", eff="2017-06-01", status="现行有效(注:2025修正,2026-01-01施行,待核)",
    scope="无人机联网系统(UOM/云系统)网络与数据安全",
    path="law/01_法律/中华人民共和国网络安全法.html", url="https://www.gov.cn/", ingested="否")
add(cat=G, title="中华人民共和国反恐怖主义法", organ="全国人大常委会",
    docno="主席令第36号(2018修正)", pub="2015-12-27", eff="2016-01-01", status="现行有效",
    scope="重点目标/大型活动上空无人机反恐管制",
    path="law/01_法律/中华人民共和国反恐怖主义法.html", url="https://www.gov.cn/", ingested="否")
add(cat=G, title="中华人民共和国国家安全法", organ="全国人大常委会",
    docno="主席令第29号", pub="2015-07-01", eff="2015-07-01", status="现行有效",
    scope="涉国家安全的低空管控总则性依据",
    path="law/01_法律/中华人民共和国国家安全法.html", url="https://www.gov.cn/", ingested="否")
add(cat=G, title="中华人民共和国测绘法", organ="全国人大常委会",
    docno="主席令第67号(2017修订)", pub="2017-04-27", eff="2017-07-01", status="现行有效",
    scope="无人机航空摄影测量的测绘资质与成果管理",
    path="law/01_法律/中华人民共和国测绘法.html", url="https://www.gov.cn/", ingested="否")
add(cat=G, title="中华人民共和国突发事件应对法", organ="全国人大常委会",
    docno="主席令(2024修订)", pub="2024-06-28", eff="2024-11-01", status="现行有效(2024版)",
    scope="应急救援/灾害监测无人机的应急征用与协同",
    path="law/01_法律/中华人民共和国突发事件应对法.html", url="https://www.gov.cn/", ingested="否")
add(cat=G, title="中华人民共和国民法典·第七编 侵权责任", organ="全国人大",
    docno="主席令第45号", pub="2020-05-28", eff="2021-01-01", status="现行有效",
    scope="无人机坠落致人损害、高度危险作业责任、隐私侵权",
    path="law/01_法律/中华人民共和国民法典-第七编侵权责任.html", url="https://www.gov.cn/", ingested="否")

# ---------- ② 行政法规（国务院/中央军委） ----------
G = "行政法规"
add(cat=G, title="无人驾驶航空器飞行管理暂行条例", organ="国务院、中央军委",
    docno="国务院令、中央军委令第761号", pub="2023-05-31", eff="2024-01-01", status="现行有效",
    scope="★民用无人机分类(微/轻/小/中/大型)、实名登记、空域、飞行活动、法律责任的核心行政法规",
    path="law/02_行政法规/无人驾驶航空器飞行管理暂行条例.html",
    url="https://www.mee.gov.cn/zcwj/gwywj/202307/t20230706_1035450.shtml", ingested="是", note="★全案地基")
add(cat=G, title="通用航空飞行管制条例", organ="国务院、中央军委",
    docno="国务院令、中央军委令第371号", pub="2003-01-10", eff="2003-05-01", status="现行有效",
    scope="通用航空(含无人机)飞行计划申请、空域使用、飞行管制",
    path="law/02_行政法规/通用航空飞行管制条例.html", url="https://www.gov.cn/", ingested="否")
add(cat=G, title="中华人民共和国飞行基本规则", organ="国务院、中央军委",
    docno="国务院、中央军委令(2007修订)", pub="2000-07-24", eff="2001-08-01", status="现行有效",
    scope="国家空域划分与飞行的基本规则(上位空域规则)",
    path="law/02_行政法规/中华人民共和国飞行基本规则.html", url="https://www.gov.cn/", ingested="否")
add(cat=G, title="中华人民共和国无线电管理条例", organ="国务院、中央军委",
    docno="国务院、中央军委令第672号", pub="2016-11-11", eff="2016-12-01", status="现行有效",
    scope="无人机测控/图传/导航频率与无线电台(站)管理",
    path="law/02_行政法规/中华人民共和国无线电管理条例.html", url="https://www.gov.cn/", ingested="否")
add(cat=G, title="民用机场管理条例", organ="国务院",
    docno="国务院令第553号(2019修订)", pub="2009-04-13", eff="2009-07-01", status="现行有效",
    scope="民用机场净空保护区，禁止无人机干扰航空器起降",
    path="law/02_行政法规/民用机场管理条例.html", url="https://www.gov.cn/", ingested="否")
add(cat=G, title="中华人民共和国民用航空器国籍登记条例", organ="国务院",
    docno="国务院令第188号", pub="1997-10-21", eff="1997-10-21", status="现行有效",
    scope="民用航空器国籍登记(适航/登记制度参照)",
    path="law/02_行政法规/中华人民共和国民用航空器国籍登记条例.html", url="https://www.gov.cn/", ingested="否")
add(cat=G, title="中华人民共和国测绘成果管理条例", organ="国务院",
    docno="国务院令第469号", pub="2006-05-27", eff="2006-09-01", status="现行有效",
    scope="无人机航测成果的汇交、保管与涉密管理",
    path="law/02_行政法规/中华人民共和国测绘成果管理条例.html", url="https://www.gov.cn/", ingested="否")
add(cat=G, title="外国民用航空器飞行管理规则", organ="国务院、中央军委",
    docno="国务院、中央军委", pub="1979-02-23", eff="1979-02-23", status="现行有效",
    scope="外国民用航空器入境飞行(边缘相关)",
    path="law/02_行政法规/外国民用航空器飞行管理规则.html", url="https://www.gov.cn/", ingested="否")

# ---------- ③ 部门规章（交通运输部/民航局，CCAR） ----------
G = "部门规章"
add(cat=G, title="民用无人驾驶航空器运行安全管理规则(CCAR-92)", organ="交通运输部/中国民航局",
    docno="交通运输部令2024年第1号", pub="2024-01-04", eff="2024-01-01", status="现行有效",
    scope="★开放类/特定类/审定类无人机运行安全；操控员、运营、适航衔接",
    path="law/03_部门规章/CCAR-92_民用无人驾驶航空器运行安全管理规则.pdf",
    url="https://www.caac.gov.cn/", ingested="是", note="★核心运行规章")
add(cat=G, title="一般运行和飞行规则(CCAR-91-R4)", organ="中国民航局",
    docno="交通运输部令(CCAR-91 R4)", pub="2021-11-08", eff="2022-01-01", status="现行有效",
    scope="民用航空器一般运行与飞行规则(通航/无人机部分条款参照)",
    path="law/03_部门规章/CCAR-91-R4_一般运行和飞行规则.pdf", url="https://www.caac.gov.cn/", ingested="否")

# ---------- ④ 规范性文件（民航局 AC/AP/MD/IB） ----------
G = "规范性文件"
add(cat=G, title="民用无人驾驶航空器经营性飞行活动管理办法(暂行)", organ="中国民航局运输司",
    docno="MD-TR-2018-01", pub="2018-05-28", eff="2018-06-01", status="现行有效",
    scope="无人机经营许可证的申请、条件与监督管理",
    path="law/04_规范性文件/MD-TR-2018-01_民用无人驾驶航空器经营性飞行活动管理办法(暂行).pdf",
    url="https://www.caac.gov.cn/", ingested="是")
add(cat=G, title="轻小无人机运行规定(试行)(AC-91-FS-2015-31)", organ="中国民航局飞标司",
    docno="AC-91-FS-2015-31", pub="2015-12-29", eff="2015-12-29", status="现行有效(部分被CCAR-92吸收)",
    scope="轻小型无人机分类(I-XI类)运行要求、云系统接入",
    path="law/04_规范性文件/AC-91-FS-2015-31_轻小无人机运行规定(试行).pdf", url="https://www.caac.gov.cn/", ingested="否")
add(cat=G, title="民用无人驾驶航空器操控员管理规定(AC-61-FS-020R3)", organ="中国民航局飞标司",
    docno="AC-61-FS-020R3", pub="2024", eff="2024", status="现行有效",
    scope="无人机操控员执照/等级、训练与考试(替代原驾驶员管理规定)",
    path="law/04_规范性文件/AC-61-FS-020R3_民用无人驾驶航空器操控员管理规定.pdf", url="https://www.caac.gov.cn/", ingested="否")
add(cat=G, title="民用无人驾驶航空器系统空中交通管理办法(MD-TM-2016-004)", organ="中国民航局空管办",
    docno="MD-TM-2016-004", pub="2016-09-21", eff="2016-09-21", status="现行有效",
    scope="无人机系统空中交通服务与空域协调",
    path="law/04_规范性文件/MD-TM-2016-004_民用无人驾驶航空器系统空中交通管理办法.pdf", url="https://www.caac.gov.cn/", ingested="否")
add(cat=G, title="民用无人驾驶航空器系统适航审定管理程序(AP-21-AA-2022-71)", organ="中国民航局适航司",
    docno="AP-21-AA-2022-71", pub="2022", eff="2022", status="现行有效",
    scope="无人机系统适航审定(型号合格审定)程序",
    path="law/04_规范性文件/AP-21-AA-2022-71_民用无人驾驶航空器系统适航审定管理程序.pdf", url="https://www.caac.gov.cn/", ingested="否")
add(cat=G, title="民用无人驾驶航空器实名制登记管理规定(AP-45-AA-2017-03)", organ="中国民航局",
    docno="AP-45-AA-2017-03", pub="2017-05-16", eff="2017-06-01", status="已废止/被取代",
    scope="250g以上无人机实名登记(旧制)",
    path="law/04_规范性文件/AP-45-AA-2017-03_民用无人驾驶航空器实名制登记管理规定.pdf", url="https://www.caac.gov.cn/", ingested="否",
    note="⚠已被 GB 46761-2025《实名登记和激活要求》(2026-05-01施行)取代，仅作历史/对比语料")
add(cat=G, title="D类(限用类)无人驾驶航空器系统失效状态(AC-21-AA-2022-40)", organ="中国民航局适航司",
    docno="AC-21-AA-2022-40", pub="2022", eff="2022", status="现行有效",
    scope="D类限用类无人机系统失效状态与安全性分析",
    path="law/04_规范性文件/AC-21-AA-2022-40_D类限用类无人驾驶航空器系统失效状态.pdf", url="https://www.caac.gov.cn/", ingested="否")
add(cat=G, title="限用类无人驾驶航空器系统适航标准(AC-21-AA-2026-44)", organ="中国民航局适航司",
    docno="AC-21-AA-2026-44", pub="2026-02-12", eff="2026-02-12", status="现行有效",
    scope="中型及最大起飞重量<3180kg大型限用类无人机型号合格审定适航要求",
    path="law/04_规范性文件/AC-21-AA-2026-44_限用类无人驾驶航空器系统适航标准.pdf",
    url="http://www.caac.gov.cn/XXGK/XXGK/GFXWJ/202602/P020260226338705668572.pdf", ingested="否")
add(cat=G, title="正常类多旋翼无人驾驶航空器系统(不载人)适航标准(AC-21-AA-2026-46)", organ="中国民航局适航司",
    docno="AC-21-AA-2026-46(民航适函〔2026〕26号)", pub="2026-04-03", eff="2026-04-03", status="现行有效",
    scope="进入融合空域或人口密集区上方飞行、不载人的正常类多旋翼无人机适航要求",
    path="law/04_规范性文件/AC-21-AA-2026-46_正常类多旋翼无人驾驶航空器系统适航标准.pdf", url="https://www.caac.gov.cn/", ingested="否")
add(cat=G, title="正常类动力提升无人驾驶航空器系统(不载人)适航标准(AC-21-AA-2026-47)", organ="中国民航局适航司",
    docno="AC-21-AA-2026-47", pub="2026", eff="2026", status="现行有效",
    scope="正常类动力提升(不载人)无人机适航要求",
    path="law/04_规范性文件/AC-21-AA-2026-47_正常类动力提升无人驾驶航空器系统适航标准.pdf", url="https://www.caac.gov.cn/", ingested="否")
add(cat=G, title="中型民用无人驾驶航空器系统适航标准及符合性指导材料(试行)(AC-92-AA-2024-02)", organ="中国民航局适航司",
    docno="AC-92-AA-2024-02", pub="2024", eff="2024", status="现行有效(注:或被AC-21-AA-2026-44替代,待核)",
    scope="中型无人机系统适航标准(试行)",
    path="law/04_规范性文件/AC-92-AA-2024-02_中型民用无人驾驶航空器系统适航标准及符合性指导材料(试行).pdf",
    url="https://www.caac.gov.cn/", ingested="否", note="⚠2026限用类适航标准生效后其中型部分可能废止，复核时效")
add(cat=G, title="民用无人驾驶航空器运行控制系统要求(AC-92-FS-002)", organ="中国民航局飞标司",
    docno="AC-92-FS-002", pub="2024", eff="2024", status="现行有效",
    scope="无人机运行控制系统技术与管理要求",
    path="law/04_规范性文件/AC-92-FS-002_民用无人驾驶航空器运行控制系统要求.pdf", url="https://www.caac.gov.cn/", ingested="否")
add(cat=G, title="无人驾驶航空器系统信息通告(IB-TM-2022-05)", organ="中国民航局空管办",
    docno="IB-TM-2022-05", pub="2022", eff="2022", status="现行有效",
    scope="无人机系统运行相关信息通告",
    path="law/04_规范性文件/IB-TM-2022-05_无人驾驶航空器系统信息通告.pdf", url="https://www.caac.gov.cn/", ingested="否")

# ---------- ⑤ 国家/行业标准（GB 强制 / MH-T 民航行标 / IB） ----------
G = "标准"
add(cat=G, title="民用无人驾驶航空器系统运行识别规范(GB 46750-2025)", organ="市场监管总局(标准委)/民航局",
    docno="GB 46750-2025", pub="2025-10-31", eff="2026-05-01", status="现行有效(强制性国标)",
    scope="★无人机运行全过程主动报送身份/位置/速度识别信息(广播式+网络式)技术要求",
    path="law/05_标准/GB 46750-2025 民用无人驾驶航空器系统运行识别规范.pdf", url="https://www.caac.gov.cn/", ingested="否")
add(cat=G, title="民用无人驾驶航空器实名登记和激活要求(GB 46761-2025)", organ="市场监管总局(标准委)/民航局",
    docno="GB 46761-2025", pub="2025-10-31", eff="2026-05-01", status="现行有效(强制性国标)",
    scope="★250g以上无人机实名登记+一机一码强制激活(替代2017实名制规定)",
    path="law/05_标准/GB 46761-2025 民用无人驾驶航空器实名登记和激活要求.pdf", url="https://www.caac.gov.cn/", ingested="否",
    note="⚠官方PDF逐字空格/多栏，自动抽取碎片严重，待Word版或人工整理后入库")
add(cat=G, title="民用无人驾驶航空器系统安全要求(GB 42590-2023)", organ="市场监管总局(标准委)/工信部提出归口",
    docno="GB 42590-2023", pub="2023-05-23", eff="2024-06-01(主要条款提前至2024-01-01)", status="现行有效(强制性国标·首项)",
    scope="★除航模外微/轻/小型无人机的研制/生产/交付/使用；规定电子围栏、远程识别、应急处置、感知避让等17项强制技术要求及试验方法；761号条例核心配套支撑标准",
    path="law/05_标准/GB 42590-2023 民用无人驾驶航空器系统安全要求.pdf",
    url="https://openstd.samr.gov.cn/bzgk/gb/newGbInfo?hcno=0DC41035BA23EF2C5B94E6482492AF1E", ingested="是",
    note="2026-08-04 OCR入库(rapidocr-onnxruntime,38页扫描件无文字层→31条chunk：第3章术语定义(微/轻/小型法定阈值)+第4章17项安全要求4.1~4.17)；第5章试验方法表格密集、检测操作细节，未逐条入库")
add(cat=G, title="民用微轻小型无人驾驶航空器运行识别最低性能要求(试行)(IB-TM-2024-01)", organ="中国民航局空管办",
    docno="IB-TM-2024-01", pub="2024", eff="2024", status="现行有效",
    scope="微/轻/小型无人机运行识别最低性能(信息通告)",
    path="law/05_标准/IB-TM-2024-01 民用微轻小型无人驾驶航空器运行识别最低性能要求(试行) 信息通告.pdf",
    url="https://www.caac.gov.cn/", ingested="否", note="与 05_标准/民用微轻小型…(试行).pdf 内容同源，注意去重")
add(cat=G, title="无人机围栏(MH-T 2008-2017)", organ="中国民航局", docno="MH/T 2008-2017", pub="2017", eff="2017",
    status="现行有效(民航行业标准)", scope="电子围栏技术要求",
    path="law/05_标准/MH-T 2008-2017 无人机围栏.pdf", url="https://www.caac.gov.cn/", ingested="否")
add(cat=G, title="无人机云系统接口数据规范(MH-T 2009-2017)", organ="中国民航局", docno="MH/T 2009-2017", pub="2017", eff="2017",
    status="现行有效(民航行业标准)", scope="无人机云系统接口数据",
    path="law/05_标准/MH-T 2009-2017 无人机云系统接口数据规范.pdf", url="https://www.caac.gov.cn/", ingested="否")
add(cat=G, title="无人机云系统数据规范(MH-T 2011-2019)", organ="中国民航局", docno="MH/T 2011-2019", pub="2019", eff="2019",
    status="现行有效(民航行业标准)", scope="无人机云系统数据",
    path="law/05_标准/MH-T 2011-2019 无人机云系统数据规范.pdf", url="https://www.caac.gov.cn/", ingested="否")
add(cat=G, title="民用无人驾驶航空器系统分布式操控员能力要求与评估(MH-T 2018-2026)", organ="中国民航局",
    docno="MH/T 2018-2026", pub="2026", eff="2026", status="现行有效(民航行业标准)", scope="分布式操控员能力与评估",
    path="law/05_标准/MH-T 2018-2026 民用无人驾驶航空器系统分布式操控员能力要求与评估.pdf", url="https://www.caac.gov.cn/", ingested="否")
add(cat=G, title="大型民用无人驾驶航空器系统操控员训练要求(MH-T 2019-2026)", organ="中国民航局",
    docno="MH/T 2019-2026", pub="2026", eff="2026", status="现行有效(民航行业标准)", scope="大型无人机操控员训练",
    path="law/05_标准/MH-T 2019-2026 大型民用无人驾驶航空器系统操控员训练要求.pdf", url="https://www.caac.gov.cn/", ingested="否")
add(cat=G, title="民用无人驾驶航空器空域信息数字化技术要求 第1部分:编码及使用(MH-T 4063.1-2026)", organ="中国民航局",
    docno="MH/T 4063.1-2026", pub="2026", eff="2026", status="现行有效(民航行业标准)", scope="低空空域信息数字化编码",
    path="law/05_标准/MH-T 4063.1-2026 民用无人驾驶航空器空域信息数字化技术要求 第1部分 编码及使用.pdf", url="https://www.caac.gov.cn/", ingested="否")
add(cat=G, title="民用无人驾驶航空器航行服务系统数据安全技术要求(MH-T 4064-2026)", organ="中国民航局",
    docno="MH/T 4064-2026", pub="2026", eff="2026", status="现行有效(民航行业标准)", scope="航行服务系统数据安全",
    path="law/05_标准/MH-T 4064-2026 民用无人驾驶航空器航行服务系统数据安全技术要求.pdf", url="https://www.caac.gov.cn/", ingested="否")
add(cat=G, title="民用无人驾驶航空器降落伞系统规范(MH-T 6140-2026)", organ="中国民航局",
    docno="MH/T 6140-2026", pub="2026", eff="2026", status="现行有效(民航行业标准)", scope="无人机降落伞系统",
    path="law/05_标准/MH-T 6140-2026 民用无人驾驶航空器降落伞系统规范.pdf", url="https://www.caac.gov.cn/", ingested="否")
add(cat=G, title="民用微轻小型无人驾驶航空器运行识别最低性能要求(试行)", organ="中国民航局空管办",
    docno="(同 IB-TM-2024-01)", pub="2024", eff="2024", status="现行有效",
    scope="微/轻/小型无人机运行识别最低性能",
    path="law/05_标准/民用微轻小型无人驾驶航空器运行识别最低性能要求(试行).pdf", url="https://www.caac.gov.cn/", ingested="否",
    note="与 IB-TM-2024-01 同源，入库时择一/去重")

# ---------- ⑥ 地方性法规/地方政府规章（来自 06 目录 JSON，自动并入） ----------
try:
    dj = json.load(open(os.path.join(KB, "law/06_地方性法规/_download_result.json"), encoding="utf-8"))
    for d in dj.get("downloaded", []):
        add(cat="地方性法规/地方规章", title=d.get("法规名",""), organ=d.get("发布机关",""),
            docno=d.get("文号",""), pub=d.get("公布日期",""), eff=d.get("生效日期",""),
            status=d.get("时效性","")+" / "+d.get("效力层级",""),
            scope="地方低空经济产业促进/飞行服务保障" ,
            path="law/06_地方性法规/"+d.get("本地文件名",""), url=d.get("源URL",""),
            ingested=("是" if "深圳" in d.get("法规名","") or "苏州" in d.get("法规名","") else "否"),
            note=d.get("备注",""))
except Exception as e:
    print("WARN 06 json", e)

# ---------- ⑦ 解读与案例（来自 07 目录 JSON，自动并入） ----------
try:
    mj = json.load(open(os.path.join(KB, "law/07_解读与案例/_manifest_解读与案例.json"), encoding="utf-8"))
    for d in mj.get("downloaded", []):
        add(cat="解读与案例", title=d.get("标题",""), organ=d.get("发布机关",""),
            docno="", pub=d.get("发布日期",""), eff="", status=d.get("类别",""),
            scope="关联:"+d.get("关联法规",""),
            path="law/07_解读与案例/"+d.get("本地文件名",""), url=d.get("源URL",""),
            ingested="否", note=d.get("备注",""))
except Exception as e:
    print("WARN 07 json", e)

# ============================================================
# 自动校准"是否已入库"：法规名(去『中华人民共和国』/括注/间隔号)命中 chunk 库则标"是"
# ============================================================
def _norm(s):
    return re.sub(r"[（(].*?[)）]", "", str(s)).replace("中华人民共和国", "").replace("·", "").replace(" ", "").strip()
_ing = set(_norm(n) for n in ingested_names if n)
for r in R:
    t = _norm(r["title"])
    if t and (t in _ing or any(len(t) > 4 and (t in n or n in t) for n in _ing)):
        r["ingested"] = "是"

# ============================================================
# 输出 CSV
# ============================================================
cols = [("序号","_idx"),("效力层级","cat"),("标题","title"),("发布机关","organ"),
        ("文号","docno"),("发布日期","pub"),("施行日期","eff"),("时效性/现行版本","status"),
        ("适用范围","scope"),("是否已入库","ingested"),("文件路径","path"),("来源URL","url"),("备注","note")]
for i,r in enumerate(R,1): r["_idx"]=i
csv_path = os.path.join(KB, "法规清单总表.csv")
with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
    w = csv.writer(f)
    w.writerow([c[0] for c in cols])
    for r in R: w.writerow([r.get(c[1],"") for c in cols])

# ============================================================
# 输出 Markdown（按效力层级分节）
# ============================================================
order = ["法律","行政法规","部门规章","规范性文件","标准","地方性法规/地方规章","解读与案例"]
md = []
md.append("# 低空经济无人机法律法规 —— 法规清单总表\n")
md.append(f"> 生成脚本：`knowledge_base/build_inventory.py`　｜　记录总数：**{len(R)}** 条　｜　对应机器可读文件：`法规清单总表.csv`\n")
md.append("> 字段与 RAG chunk 元数据对齐：效力层级 / 标题 / 发布机关 / 文号 / 发布日期 / 施行日期 / 时效性 / 适用范围 / 是否已入库 / 文件路径 / 来源URL\n")
# 统计
from collections import Counter
cc = Counter(r["cat"] for r in R)
ic = Counter(r["ingested"] for r in R)
md.append("\n## 汇总统计\n")
md.append("| 效力层级 | 条目数 |\n|---|---|")
for k in order:
    if cc.get(k): md.append(f"| {k} | {cc[k]} |")
md.append(f"| **合计** | **{len(R)}** |\n")
md.append(f"\n入库状态：已入库(切分成chunk) **{ic.get('是',0)}** 部 ｜ 仅原始文档待解析 **{ic.get('否',0)}** 部\n")

for k in order:
    rows = [r for r in R if r["cat"]==k]
    if not rows: continue
    md.append(f"\n## {k}（{len(rows)}）\n")
    md.append("| # | 标题 | 发布机关 | 文号 | 发布/施行 | 时效性 | 适用范围 | 入库 | 文件路径 |")
    md.append("|---|---|---|---|---|---|---|---|---|")
    for r in rows:
        pe = (r.get("pub","") or "") + ("→"+r["eff"] if r.get("eff") else "")
        cell = lambda s: str(s or "").replace("|","／").replace("\n"," ")
        md.append("| {i} | {t} | {o} | {d} | {pe} | {s} | {sc} | {ing} | `{p}` |".format(
            i=r["_idx"], t=cell(r["title"]), o=cell(r["organ"]), d=cell(r["docno"]),
            pe=cell(pe), s=cell(r["status"]), sc=cell(r["scope"]), ing=cell(r["ingested"]), p=cell(r["path"])))
    # 备注单列（如有）
    notes = [r for r in rows if r.get("note")]
    if notes:
        md.append("\n备注：")
        for r in notes: md.append(f"- **{r['title']}**：{r['note']}")

open(os.path.join(KB,"法规清单总表.md"),"w",encoding="utf-8").write("\n".join(md))

# ============================================================
# 覆盖率自检：law/01-05 目录里每个文件都应在清单中
# ============================================================
print("=== 覆盖率自检 ===")
listed = set(r["path"] for r in R)
missing = []
for d in ["01_法律","02_行政法规","03_部门规章","04_规范性文件","05_标准"]:
    for fp in glob.glob(os.path.join(KB,"law",d,"*")):
        if os.path.isfile(fp) and rel(fp) not in listed:
            missing.append(rel(fp))
if missing:
    print("⚠ 有文件未登记入清单：")
    for m in missing: print("   ", m)
else:
    print("✅ 01-05 目录文件已全部登记")
# 反向：清单里 path 指向的文件是否存在
for r in R:
    if r["path"] and not os.path.exists(os.path.join(KB, r["path"])):
        print("⚠ 清单路径不存在：", r["path"])

print(f"\n✅ 已生成 法规清单总表.csv / .md（{len(R)} 条）")
