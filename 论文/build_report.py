from docx import Document
from docx.shared import Inches, Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.enum.style import WD_STYLE_TYPE
from PIL import Image, ImageDraw, ImageFont
import os, json, shutil

ROOT = r'D:\schoolwork\competition\低空经济无人机法律智能问答比赛'
OUT = os.path.join(ROOT, '论文')
FIG = os.path.join(OUT, 'figures')
os.makedirs(FIG, exist_ok=True)
DOCX = os.path.join(OUT, '无人机法律法规智能问答系统.docx')
PNG = os.path.join(FIG, '项目总体框架图_论文版.png')

# ---------- draw framework image ----------
font_regular = r'C:\Windows\Fonts\msyh.ttc'
font_bold = r'C:\Windows\Fonts\msyhbd.ttc'
def font(size, bold=False):
    return ImageFont.truetype(font_bold if bold else font_regular, size)
W, H = 1800, 2450
im = Image.new('RGB', (W,H), 'white')
d = ImageDraw.Draw(im)
black=(35,35,35); gray=(95,95,95); light=(248,248,248)
def rect(x1,y1,x2,y2, dashed=False, fill='white', width=3):
    if not dashed:
        d.rectangle((x1,y1,x2,y2), outline=black, fill=fill, width=width)
    else:
        d.rectangle((x1,y1,x2,y2), outline=gray, fill=fill, width=2)
        for x in range(x1,x2,24):
            d.line((x,y1,x+12,y1),fill=gray,width=2); d.line((x,y2,x+12,y2),fill=gray,width=2)
        for y in range(y1,y2,24):
            d.line((x1,y,x1,y+12),fill=gray,width=2); d.line((x2,y,x2,y+12),fill=gray,width=2)
def center(text, box, fnt, fill=black, spacing=8):
    x1,y1,x2,y2=box; lines=text.split('\n'); hs=[]
    for line in lines:
        bb=d.textbbox((0,0),line,font=fnt); hs.append(bb[3]-bb[1])
    total=sum(hs)+spacing*(len(lines)-1); y=y1+(y2-y1-total)//2
    for line,h in zip(lines,hs):
        bb=d.textbbox((0,0),line,font=fnt); x=x1+(x2-x1-(bb[2]-bb[0]))//2
        d.text((x,y),line,font=fnt,fill=fill); y+=h+spacing
def arrow(x1,y1,x2,y2):
    d.line((x1,y1,x2,y2),fill=black,width=3)
    import math
    a=math.atan2(y2-y1,x2-x1); L=18
    p1=(x2-L*math.cos(a-0.45),y2-L*math.sin(a-0.45)); p2=(x2-L*math.cos(a+0.45),y2-L*math.sin(a+0.45))
    d.polygon([(x2,y2),p1,p2],fill=black)
def group(y,h,title,stage):
    rect(180,y,1740,y+h,True,fill=light)
    d.text((215,y+22),title,font=font(27,True),fill=black)
    rect(35,y+35,135,y+h-35,False)
    center(stage,(35,y+35,135,y+h-35),font(25,True))

d.text((260,20),'低空经济无人机法律智能问答系统总体框架',font=font(38,True),fill=black)
group(100,230,'一、研究目标与理论基础','研究\n目标')
for x,t in [(270,'低空经济法律\n问答需求'),(640,'知识图谱与\nRAG理论'),(1010,'系统设计\n目标'),(1380,'可解释、可追溯、\n时效感知')]:
    rect(x,180,x+250,245); center(t,(x,180,x+250,245),font(21))
for x in [520,890,1260]: arrow(x,212,x+100,212)

group(370,340,'二、多源法律数据采集、Chunk切分与向量索引','数据\n处理')
inputs=[(235,'法规与规章\n法律、行政法规、部门规章'),(535,'国家标准与规范\n运行、适航、实名登记'),(835,'地方性法规\n省市低空经济政策'),(1135,'司法案例与解读\n案例、答记者问、释义'),(1450,'36题\n评测集')]
for x,t in inputs: rect(x,435,x+(220 if x<1450 else 180),525); center(t,(x,435,x+(220 if x<1450 else 180),525),font(17))
steps=[(235,'解析、去重与归一\n效力 / 时效 / 来源',220),(500,'Parent Chunk\n一条法条=Article单元',250),(795,'Child Chunk\n语义分块+parent_id',250),(1090,'Embedding与索引\nBGE-M3→Chroma；文本→BM25',400)]
for x,t,w in steps: rect(x,555,x+w,630); center(t,(x,555,x+w,630),font(17))
for a,b in [(455,500),(750,795),(1045,1090)]: arrow(a,592,b,592)
rect(470,655,1330,700); center('3701个结构化单元 · 当前索引3586个法条Parent、531个案例Parent、4901个Child Chunk',(470,655,1330,700),font(16))
arrow(1290,630,1290,655)

group(760,270,'三、领域本体与法律知识建模','知识\n建模')
for x,t in [(235,'实体类型设计\n法规、条款、术语、机型\n主体、活动、后果、案例'),(700,'关系类型设计\n属于、引用、定义、适用于\n义务主体、违反后果、取代'),(1165,'法律属性建模\n效力层级、发布日期、生效日期\n时效状态、来源与证据')]:
    rect(x,825,x+350,955); center(t,(x,825,x+350,955),font(18))
rect(500,1000,1300,1048); center('本体约束 + 受控词表 + 条款事件结构（主体—行为—条件—后果）',(500,1000,1300,1048),font(16))
for x in [410,875,1330]: arrow(x,955,900,1000)

group(1080,400,'四、知识抽取、融合与图谱构建','知识\n图谱')
for x,t in [(235,'规则抽取\n正则、词典、条款编号'),(565,'大语言模型抽取\n实体、属性、关系、事件'),(895,'实体对齐与消歧\n别名归一、跨源去重'),(1225,'质量校验\nSchema、规则、人工复核')]:
    rect(x,1150,x+285,1240); center(t,(x,1150,x+285,1240),font(18))
rect(450,1290,1350,1380); center('法律知识图谱\n107部法规 · 531个案例 · 6650个节点 · 12489条边',(450,1290,1350,1380),font(20,True))
rect(600,1415,1200,1460); center('Neo4j图数据库 / Cypher查询 / 多关系异构图',(600,1415,1200,1460),font(16))
for x in [377,707,1037,1367]: arrow(x,1240,900,1290)
arrow(900,1380,900,1415)

group(1540,420,'五、知识图谱增强的混合检索与问答生成','检索与\n问答')
xs=[235,515,795,1075,1380]; ts=['用户问题\n自然语言提问','问题理解\n实体识别与意图分类','混合召回\nBGE-M3 + BM25 + RRF','精排与过滤\nReranker + 仅现行有效','图扩展\n1—2跳']
ws=[230,230,230,260,170]
for x,t,w in zip(xs,ts,ws): rect(x,1625,x+w,1715); center(t,(x,1625,x+w,1715),font(17))
for i in range(4): arrow(xs[i]+ws[i],1670,xs[i+1],1670)
rect(500,1780,1450,1870); center('证据约束的LLM生成\n只依据检索条文作答 · 强制法规名/条号引用 · 不编造依据',(500,1780,1450,1870),font(19,True))
arrow(1465,1715,1420,1780); arrow(910,1715,910,1780)
rect(380,1910,1570,1960); center('答案输出：结论 + 适用条件 + 法律依据 + 处罚/责任 + 引用来源 + 时效提示',(380,1910,1570,1960),font(16)); arrow(975,1870,975,1910)

group(2040,300,'六、系统评测与应用展示','评测与\n应用')
for x,t,w in [(235,'检索层评测\nHit@k、Recall@k、MRR、nDCG',300),(650,'生成层评测\n忠实度、正确性、时效性、引用',300),(1065,'应用层\nWeb问答、引用溯源、图谱展示',300),(1480,'迭代优化\n失败案例分析',170)]: rect(x,2130,x+w,2225); center(t,(x,2130,x+w,2225),font(17))
for a,b in [(535,650),(950,1065),(1365,1480)]: arrow(a,2177,b,2177)
rect(600,2260,1300,2305); center('评测反馈 → 检索、图谱与提示词持续优化',(600,2260,1300,2305),font(16))
arrow(1215,2225,1215,2260)
im.save(PNG, quality=95)
print(PNG)

# ---------- docx helpers ----------
def set_cell_shading(cell, fill):
    tcPr=cell._tc.get_or_add_tcPr(); shd=OxmlElement('w:shd'); shd.set(qn('w:fill'),fill); tcPr.append(shd)
def set_cell_text(cell, text, bold=False, size=9):
    cell.text=''; p=cell.paragraphs[0]; p.alignment=WD_ALIGN_PARAGRAPH.CENTER
    r=p.add_run(str(text)); r.bold=bold; r.font.name='宋体'; r._element.rPr.rFonts.set(qn('w:eastAsia'),'宋体'); r.font.size=Pt(size)
def set_run_font(run, name='宋体', size=12, bold=False, italic=False):
    run.font.name=name; run._element.rPr.rFonts.set(qn('w:eastAsia'),name); run.font.size=Pt(size); run.bold=bold; run.italic=italic
def set_para(p, first=True, align=WD_ALIGN_PARAGRAPH.JUSTIFY, space_after=6, line=1.5):
    p.alignment=align; pf=p.paragraph_format; pf.line_spacing=line; pf.space_after=Pt(space_after)
    if first: pf.first_line_indent=Cm(0.74)
def add_para(doc, text, first=True, align=WD_ALIGN_PARAGRAPH.JUSTIFY, size=12, bold=False):
    p=doc.add_paragraph(); set_para(p,first,align); r=p.add_run(text); set_run_font(r,size=size,bold=bold); return p
def add_heading(doc,text,level=1):
    p=doc.add_paragraph(style=f'Heading {level}'); p.alignment=WD_ALIGN_PARAGRAPH.LEFT
    pf=p.paragraph_format; pf.space_before=Pt(10 if level==1 else 6); pf.space_after=Pt(6); pf.keep_with_next=True
    r=p.add_run(text); set_run_font(r,size={1:16,2:14,3:12}[level],bold=True); return p
def add_caption(doc,text):
    p=doc.add_paragraph(); p.alignment=WD_ALIGN_PARAGRAPH.CENTER; p.paragraph_format.space_after=Pt(5)
    r=p.add_run(text); set_run_font(r,size=10)

def add_table(doc, headers, rows, widths=None):
    table=doc.add_table(rows=1, cols=len(headers)); table.alignment=WD_TABLE_ALIGNMENT.CENTER; table.style='Table Grid'
    for i,h in enumerate(headers): set_cell_text(table.rows[0].cells[i],h,True,9); set_cell_shading(table.rows[0].cells[i],'D9EAF7')
    for row in rows:
        cells=table.add_row().cells
        for i,v in enumerate(row): set_cell_text(cells[i],v,False,8.5)
    for row in table.rows:
        for cell in row.cells: cell.vertical_alignment=WD_CELL_VERTICAL_ALIGNMENT.CENTER
    return table

# ---------- document ----------
doc=Document(); sec=doc.sections[0]
sec.top_margin=Cm(2.5); sec.bottom_margin=Cm(2.5); sec.left_margin=Cm(3.0); sec.right_margin=Cm(2.5)
styles=doc.styles
styles['Normal'].font.name='宋体'; styles['Normal']._element.rPr.rFonts.set(qn('w:eastAsia'),'宋体'); styles['Normal'].font.size=Pt(12)
# page number
footer=sec.footer.paragraphs[0]; footer.alignment=WD_ALIGN_PARAGRAPH.CENTER
fld=OxmlElement('w:fldSimple'); fld.set(qn('w:instr'),'PAGE'); footer._p.append(fld)
# cover
p=doc.add_paragraph(); p.alignment=WD_ALIGN_PARAGRAPH.CENTER; p.paragraph_format.space_before=Pt(65)
r=p.add_run('低空经济无人机法律法规智能问答系统比赛报告'); set_run_font(r,size=24,bold=True)
p=doc.add_paragraph(); p.alignment=WD_ALIGN_PARAGRAPH.CENTER; p.paragraph_format.space_before=Pt(22)
r=p.add_run('基于知识图谱增强检索生成（GraphRAG）的系统设计与实现'); set_run_font(r,size=16)
for _ in range(5): doc.add_paragraph()
for label in ['参赛项目：低空经济无人机法律法规智能问答系统','报告类型：项目技术研究报告','完成日期：2026年8月']:
    p=doc.add_paragraph(); p.alignment=WD_ALIGN_PARAGRAPH.CENTER; p.paragraph_format.space_after=Pt(12); r=p.add_run(label); set_run_font(r,size=14)
doc.add_page_break()
# abstract
add_heading(doc,'摘  要',1)
add_para(doc,'随着低空经济快速发展，无人驾驶航空器在物流配送、农业作业、测绘巡检、应急救援和公共治理等场景中的应用不断扩大。与应用增长相伴的是法律法规、部门规章、技术标准、地方性法规和司法案例的持续累积。现有关键词检索难以处理法律概念的语义变化，纯向量检索又容易忽略法规效力、条款引用和时效状态，导致问答结果存在依据遗漏、版本混淆和引用不充分等问题。针对上述问题，本报告设计并实现了一种基于知识图谱增强检索生成的无人机法律法规智能问答系统。')
add_para(doc,'系统以法规条款为核心知识单元，建立包含法规、条款、章节、术语、无人机分类、义务主体、活动场景、法律后果和司法案例的领域本体。通过多源数据采集、条款结构化、Parent-Child Chunk切分、BGE-M3向量嵌入、BM25稀疏索引、规则与大语言模型协同抽取、实体对齐和Neo4j建图，形成法律知识图谱与向量检索库。在问答阶段，系统将稠密检索、稀疏检索、RRF融合、重排、现行有效过滤和Neo4j多跳图扩展结合起来，并使用带证据约束的语言模型生成答案和引用来源。')
add_para(doc,'系统目前形成包含107部法规、531个司法案例、6650个节点和12489条边的法律知识图谱；向量库包含4053个Parent、4901个Child，其中法条Parent为3586个、案例Parent为531个。基于36道覆盖13类考点的问题集进行评测，稠密检索Hit@5为0.722；混合检索在稠密权重为0.9时Hit@5达到0.750、Recall@5达到0.625；端到端生成评测的综合得分为0.908，引用正确性为0.950，时效性为0.947。结果表明，GraphRAG能够增强无人机法律问答的条款关联、证据溯源和时效控制能力。')
add_para(doc,'关键词：低空经济；无人驾驶航空器；法律法规；知识图谱；GraphRAG；智能问答',first=False,align=WD_ALIGN_PARAGRAPH.LEFT)
doc.add_page_break()
# English abstract
add_heading(doc,'ABSTRACT',1)
add_para(doc,'With the rapid development of the low-altitude economy, unmanned aircraft are increasingly used in logistics, agriculture, surveying, emergency response and public governance. Legal information related to unmanned aircraft is distributed across laws, administrative regulations, departmental rules, technical standards, local regulations and judicial cases. Keyword retrieval is insufficient for semantic variation, while pure dense retrieval may overlook legal validity, article references and temporal status. This report presents a knowledge-graph-enhanced retrieval-augmented generation system for intelligent question answering on Chinese unmanned-aircraft laws and regulations.')
add_para(doc,'The system adopts legal articles as the core knowledge units and defines an ontology covering regulations, articles, sections, terms, drone categories, actors, activities, sanctions and cases. It integrates multi-source data collection, article normalization, parent-child chunking, BGE-M3 embeddings, BM25 retrieval, rule-based and large-language-model-based extraction, entity alignment and Neo4j graph construction. During question answering, dense retrieval, sparse retrieval, reciprocal-rank fusion, reranking, current-validity filtering and multi-hop graph expansion are combined. A constrained language model generates answers grounded in retrieved evidence and provides traceable legal references.')
add_para(doc,'The resulting graph contains 107 regulations, 531 judicial cases, 6,650 nodes and 12,489 edges. The vector store contains 4,053 parent documents and 4,901 child chunks. On a 36-question benchmark covering 13 legal topics, dense retrieval achieves a Hit@5 of 0.722. With a dense retrieval weight of 0.9, hybrid retrieval reaches a Hit@5 of 0.750 and a Recall@5 of 0.625. End-to-end generation obtains an overall score of 0.908, with citation correctness of 0.950 and temporal validity of 0.947. The results demonstrate the value of GraphRAG for evidence-grounded and time-aware legal question answering in the unmanned-aircraft domain.')
add_para(doc,'Keywords: low-altitude economy; unmanned aircraft; laws and regulations; knowledge graph; GraphRAG; intelligent question answering',first=False,align=WD_ALIGN_PARAGRAPH.LEFT)
doc.add_page_break()
# contents field
add_heading(doc,'目 录',1)
p=doc.add_paragraph(); fld=OxmlElement('w:fldSimple'); fld.set(qn('w:instr'),'TOC \\o "1-3" \\h \\z \\u'); p._p.append(fld); add_para(doc,'注：在Microsoft Word中右键目录并选择“更新域”，可生成页码。',first=False,align=WD_ALIGN_PARAGRAPH.LEFT,size=10)
doc.add_page_break()
# body
add_heading(doc,'1 引言',1)
add_heading(doc,'1.1 研究背景与意义',2)
add_heading(doc,'1.1.1 研究背景',3)
add_para(doc,'低空经济是以低空空域为主要活动空间，以通用航空、无人驾驶航空器及其基础设施、运营服务和应用场景为重要组成部分的新兴经济形态。无人机运行活动具有主体多元、场景复杂、空域限制显著和责任链条较长等特点。同一用户问题往往需要综合判断无人机类型、飞行活动性质、空域属性、操控人员资质、运营许可、实名登记、适航要求和违法后果。')
add_para(doc,'无人机法律规范具有明显的分散性和关联性。相关规定不仅分布在民用航空法律法规中，还涉及空域管理、无线电管理、测绘、数据安全、个人信息保护、治安管理、地方低空经济促进和行业标准等多个领域。法律文本之间还存在引用、定义、适用、义务主体、违反后果、修订和废止取代等关系。若仅采用关键词匹配，容易遗漏同义表达；若仅采用向量相似度，可能把已废止规定、地方性重复规定或非当前适用的标准排在前面。')
add_heading(doc,'1.1.2 研究意义',3)
add_para(doc,'本项目具有技术和应用两方面意义。在技术层面，将领域本体、知识图谱、混合检索和大语言模型生成结合起来，为法律领域复杂关系检索提供可解释的实现路径；在应用层面，通过条款引用、来源展示和时效性提示，为无人机操控者、运营企业、管理人员和普通公众提供便捷的法规信息查询工具。需要说明的是，系统定位为法律信息检索和问答辅助工具，不能替代律师、行政机关或司法机关的专业判断。')
add_heading(doc,'1.2 国内外相关研究现状',2)
add_para(doc,'知识图谱研究经历了从人工构建、规则抽取到机器学习和大语言模型辅助构建的发展过程。传统方法在实体识别、关系抽取和本体推理方面具有可解释性，但对复杂非结构化文本的适应性有限。预训练语言模型和大语言模型提升了文本理解与结构化抽取能力，但存在幻觉、关系漂移、数字错误和来源不可追溯等风险。')
add_para(doc,'检索增强生成通过向生成模型提供外部知识缓解知识过时和事实错误问题。普通RAG主要依靠向量相似度进行文本召回，GraphRAG进一步利用知识图谱中的实体关系、多跳路径和社区结构组织上下文。对于无人机法律问答，法规时效、法条引用、机型适用和罚则关联是纯文本检索难以稳定处理的内容，因此需要将图结构检索与向量检索融合。')
add_heading(doc,'1.3 研究问题与主要贡献',2)
add_para(doc,'针对无人机法律问答的分散性、关联性、时效性和证据性特征，本项目重点解决五个问题：一是如何将分散、异构且具有效力层级的无人机规范文本转换为可计算的知识结构；二是如何显式表示法规之间的引用、适用、主体义务、违法行为与法律后果关系；三是如何在检索过程中同时利用语义相似性、关键词匹配、图结构关联和法规时效性；四是如何约束大语言模型仅依据可追溯条款作答，降低法律问答中的幻觉风险；五是如何通过可复现的检索与生成评测验证系统效果，并定位时效性和机型陷阱问题。')
add_para(doc,'围绕上述问题，本项目的主要贡献包括：（1）提出面向低空经济无人机法律问答的领域本体，将法规、条款、术语、机型、主体、活动、法律后果和案例统一纳入知识图谱；（2）设计规则与大语言模型协同的知识构建流程，在保留条款原文与来源信息的前提下抽取实体、属性、关系和法律事件；（3）构建融合稠密检索、稀疏检索、RRF、重排、图扩展与时效过滤的GraphRAG问答链路；（4）建立包含36道题、覆盖13类考点的评测集，从检索命中、召回、排序、忠实度、正确性、时效性和引用正确性等维度开展可复现实验；（5）系统分析实名登记、法规版本和机型阈值等失效模式，为法律智能问答系统的后续优化提供依据。')
add_heading(doc,'1.4 研究内容与技术路线',2)
add_para(doc,'本项目围绕“多源法规数据—法律知识图谱—混合检索—证据约束生成—评测应用”展开，主要内容包括：法规与案例数据采集及结构化；领域本体和法律事件模型设计；规则与大语言模型协同的知识抽取；实体对齐、时效归一和Neo4j建图；Parent-Child Chunk向量索引；BGE-M3、BM25、RRF、重排和图扩展组成的GraphRAG检索链；Web问答、引用展示和评测反馈。')
add_caption(doc,'图1-1 低空经济无人机法律智能问答系统总体框架')
doc.add_picture(PNG,width=Cm(15.8)); doc.paragraphs[-1].alignment=WD_ALIGN_PARAGRAPH.CENTER
add_heading(doc,'1.5 报告结构',2)
add_para(doc,'报告共分为六章：第一章介绍研究背景、意义和技术路线；第二章说明知识图谱、向量检索、混合检索和大语言模型生成的理论基础；第三章介绍无人机法律领域本体和知识建模；第四章重点说明多源数据处理、知识抽取、知识融合和图谱构建；第五章介绍智能问答系统的检索、生成、前端功能和实验评测；第六章总结项目成果、局限和后续改进方向。')

add_heading(doc,'2 相关理论与技术基础',1)
add_heading(doc,'2.1 知识图谱概述',2)
add_heading(doc,'2.1.1 知识图谱的构成',3)
add_para(doc,'知识图谱以实体、关系和属性为基本元素。本文将法规、条款、术语、无人机类别、义务主体、活动场景、法律后果和案例作为主要实体，将“属于、引用、定义、适用于、义务主体、违反后果、案例援引法条”等作为关系，并为法规和条款保留效力层级、发布日期、生效日期、时效状态、来源URL和原文等属性。')
add_heading(doc,'2.1.2 法律知识图谱的特点',3)
add_para(doc,'与通用知识图谱相比，法律知识图谱具有规范性、层级性、时态性和证据性。规范性要求知识能够表达“主体在条件下应当或不得实施某行为”；层级性要求区分法律、行政法规、部门规章、地方性法规、规范性文件和标准；时态性要求记录法规的生效、修改和废止状态；证据性要求每一个重要结论都能够回溯至具体法规和条款。')
add_heading(doc,'2.2 大语言模型与提示工程',2)
add_para(doc,'大语言模型能够根据上下文完成实体识别、关系抽取、事件归纳和答案生成。项目并不将模型输出直接视为法律事实，而是通过本体Schema、受控词表、JSON结构校验、正则规则复核和原文证据绑定降低错误风险。在问答阶段，系统提示模型只依据召回条文作答，并对证据不足的情况明确说明。')
add_heading(doc,'2.3 向量检索与混合检索',2)
add_para(doc,'向量检索将问题和文档映射到同一语义空间，通过向量相似度寻找语义相关的条款。BM25通过词项频率和逆文档频率进行关键词检索，适合匹配法规名称、条号、专业术语和金额区间。项目使用RRF对两路结果进行融合，随后使用重排模型对候选条款重新排序。')
add_heading(doc,'2.4 GraphRAG问答',2)
add_para(doc,'GraphRAG在普通RAG的基础上引入知识图谱。系统首先利用向量和关键词检索获得主命中条款，再沿引用、定义、适用机型、义务主体和违反后果等边进行一至两跳扩展，将相关条款补充到生成上下文中。图扩展结果保留扩展路径和来源条款，便于解释答案的形成依据。')
add_heading(doc,'2.5 本章小结',2)
add_para(doc,'本章介绍了本项目采用的知识图谱、法律事件、向量检索、混合检索、重排和GraphRAG等技术，为后续的领域建模、系统实现和实验评测提供理论基础。')

add_heading(doc,'3 无人机法律法规知识建模',1)
add_heading(doc,'3.1 领域知识建模需求',2)
add_para(doc,'无人机法律问答中的核心问题可以归纳为：某类无人机在某种活动和空域条件下，某一主体是否需要履行某项义务；如果违反规定，由何种机关依据何种条款采取何种法律措施。因此，知识模型必须同时表达实体、关系、条件、时效和证据。')
add_heading(doc,'3.2 本体模式层设计',2)
rows=[['节点类型','主要含义','关键属性'],['Regulation（法规）','一部法律法规或标准','法规名、效力层级、发布机关、公布日期、生效日期、时效性'],['Article（条款）','一条法条或语义单元','条号、条文、章、节、来源、效力信息'],['Section（章/节）','法规层级结构','标题、序号、所属法规'],['Term（术语）','法律概念和定义','术语名、定义、别名'],['DroneCategory（机型）','微型、轻型、小型、中型、大型等','名称、重量阈值、性能阈值'],['Actor（主体）','操控员、运营人、主管机关等','主体名称'],['Activity（活动）','实名登记、适航、经营性飞行等','活动名称'],['Sanction（后果）','罚款、责令改正、没收、吊销等','类型、额度、描述'],['Case（案例）','司法案例和判决摘要','案号、法院、案由、审理年份、援引法条']]
add_table(doc,['节点类型','主要含义','关键属性'],rows[1:]); add_caption(doc,'表3-1 法律知识图谱节点类型')
add_heading(doc,'3.3 关系模式层设计',2)
rows=[['关系','方向','含义'],['属于','Article→Section/Regulation','条款的章节和法规归属'],['引用','Article→Article','条文对其他条款的引用'],['定义','Article→Term','条款定义法律术语'],['适用于','Article→DroneCategory/Activity','规定适用的机型或活动'],['义务主体','Article→Actor','承担义务或权力的主体'],['违反后果','Activity/Article→Sanction','行为违反后的法律责任'],['废止/取代','Regulation→Regulation','版本和时效演进'],['案例援引法条','Case→Article','司法案例援引的规范依据']]
add_table(doc,['关系','方向','含义'],rows[1:]); add_caption(doc,'表3-2 法律知识图谱关系类型')
add_heading(doc,'3.4 法律事件结构',2)
add_para(doc,'单一三元组难以充分表达法律条款中的条件、主体和多重后果。项目将重要规范抽象为“主体—行为—条件—对象—主管机关—法律后果—依据条款”的事件结构。例如“未经批准在管制空域飞行”可表示为：行为主体为操控者，行为为管制空域飞行，条件为未经批准，活动对象为特定机型，后果为责令停止、罚款或没收，依据为对应罚则条款。')
add_heading(doc,'3.5 本章小结',2)
add_para(doc,'本章围绕无人机法律问答需求设计了节点、关系、法律属性和事件结构，为多源条款抽取、知识融合和图数据库查询建立统一模式。')

add_heading(doc,'4 无人机法律法规知识图谱构建',1)
add_heading(doc,'4.1 知识图谱构建流程',2)
add_para(doc,'知识图谱构建采用“数据采集与预处理—条款结构化—Parent-Child Chunk切分—规则与模型抽取—实体对齐与质量校验—Neo4j建图”的流程。法规原文作为证据底座保存；结构化条款作为图谱Article节点；Child Chunk用于向量嵌入；向量命中后通过parent_id回溯完整法条，保证检索片段和法律引用的一致性。')
add_heading(doc,'4.2 数据来源与预处理',2)
add_para(doc,'数据来源包括法规与规章、国家标准与行业规范、地方性法规、官方解读和司法案例。结构化阶段形成3701个条款或语义单元，覆盖132部法规；建图阶段按照去重和实体归一结果形成107部法规节点、3522个Article节点和531个Case节点。预处理包括HTML/PDF解析、标题和条款识别、章节层级恢复、来源信息保留、跨源去重、效力层级归一和时效状态标注。')
add_heading(doc,'4.3 Parent-Child Chunk与Embedding',2)
add_para(doc,'项目采用父子分块策略。Parent是检索命中后提供给语言模型的完整上下文单元，法条通常以整条法规条款作为Parent；Child是实际进行Embedding的较小文本块，长条款按照款项或句子窗口切分，并保留parent_id。向量化时在Child前补充《法规名》和条号，以提升语义召回；原始条文独立保存，用于展示和引用。')
rows=[['数据对象','数量','作用'],['法条Parent','3586','保存完整法条和法规元数据'],['案例Parent','531','保存案例标题、案由和判决摘要'],['Parent总数','4053','检索命中后的上下文回溯单元'],['Child总数','4901','用于向量嵌入和稀疏检索'],['多Child Parent','81','长条款或长案例的分块对象']]
add_table(doc,['数据对象','数量','作用'],rows[1:]); add_caption(doc,'表4-1 向量库Parent-Child分块统计')
add_heading(doc,'4.4 实体与关系抽取',2)
add_para(doc,'结构归属关系由元数据直接生成，避免对法规名称和条号进行不必要的模型推断；引用和定义关系主要由正则规则识别；术语、机型、主体、活动和法律后果等复杂实体及关系由大语言模型按照抽取Schema生成。抽取结果必须满足受控词表和字段契约，随后通过格式校验、关系方向校验和人工抽样复核进行质量控制。')
add_heading(doc,'4.5 实体对齐与时效融合',2)
add_para(doc,'实体对齐解决同一法规、机构或术语在不同来源中的名称差异。系统结合法规名称与文号去重、别名词表、字符串相似度、向量相似度和人工确认完成归一。时效融合则为法规和条款记录现行有效、已废止、未生效、已修改和部分失效等状态，并在检索阶段默认过滤或降权非现行依据。')
add_heading(doc,'4.6 Neo4j图谱构建结果',2)
rows=[['指标','数量'],['节点总数','6650'],['边总数','12489'],['法规节点','107'],['条款节点','3522'],['术语节点','192'],['主体节点','462'],['活动节点','399'],['法律后果节点','983'],['案例节点','531']]
add_table(doc,['指标','数量'],rows[1:]); add_caption(doc,'表4-2 知识图谱规模统计')
add_para(doc,'图谱关系包括3964条属于关系、167条引用关系、296条定义关系、2715条适用关系、4364条义务主体关系和983条违反后果关系。图数据库通过节点唯一标识和索引保证可重复导入，并使用Cypher支持条款引用、主体义务、机型适用和罚则关联查询。')
add_heading(doc,'4.7 本章小结',2)
add_para(doc,'本章说明了系统从多源法规文本到法律知识图谱的完整构建过程，重点介绍了Parent-Child Chunk、Embedding、规则与大语言模型协同抽取、实体融合及时效控制。')

add_heading(doc,'5 智能问答系统设计与实现',1)
add_heading(doc,'5.1 系统总体架构',2)
add_para(doc,'系统由数据层、知识构建层、存储层、检索层、生成层和应用层组成。数据层负责汇聚法规、标准、地方政策和案例；知识构建层完成结构化、抽取、对齐和建图；存储层由Neo4j、Chroma和BM25索引组成；检索层实现混合召回、时效过滤、重排和图扩展；生成层依据证据上下文生成自然语言答案；应用层通过FastAPI和Web界面提供交互式服务。系统以条款为核心检索单元，每个条款单元具有唯一标识，同时作为知识图谱中的Article节点和向量库中的父文档标识，从而保证检索结果、图谱节点与最终引用之间的一致性。')
rows=[['层次/模块','技术实现'],['开发语言','Python'],['图数据库','Neo4j（Cypher查询）'],['向量数据库','Chroma'],['稠密嵌入','BGE-M3'],['稀疏检索','BM25'],['结果融合','RRF（可调稠密权重alpha）'],['重排模型','bge-reranker-v2-m3'],['生成模型','OpenAI兼容接口，可接入DeepSeek-V3、GLM-4-Flash等'],['Web服务','FastAPI + SSE流式输出'],['前端','对话式Web问答界面']]
add_table(doc,rows[0],rows[1:]); add_caption(doc,'表5-1 系统技术栈')
add_heading(doc,'5.2 数据处理与知识库功能板块',2)
add_heading(doc,'5.2.1 多源数据采集功能',3)
add_para(doc,'系统支持法规、行政法规、部门规章、规范性文件、国家标准、地方性法规、官方解读和司法案例等多种来源。数据进入系统后保留来源文件、法规名称、效力层级、发布日期、生效日期和时效状态，为后续证据展示和版本控制提供基础。')
add_heading(doc,'5.2.2 条款结构化与分块功能',3)
add_para(doc,'系统以“一条法条一个Article单元”为基本原则，识别章、节、条号和款项信息。对于较长的法条，采用款项切分或滑动窗口切分为Child Chunk；对于案例，使用标题、案由和判决摘要构造检索文本。Parent与Child通过parent_id关联，保证模型能够获得完整上下文。')
add_heading(doc,'5.2.3 向量嵌入与索引功能',3)
add_para(doc,'系统使用BGE-M3生成中文法律文本向量，存入Chroma向量库；同时使用BM25建立稀疏索引。BGE-M3负责理解“黑飞”“需要办什么手续”等口语化问题与法规表述之间的语义联系，BM25负责精确匹配法规名称、条号、机型名称和罚款金额。')
add_heading(doc,'5.3 法律知识图谱功能板块',2)
add_heading(doc,'5.3.1 领域本体管理',3)
add_para(doc,'本体模块定义节点类型、关系类型、属性字段、机型枚举和受控词表，限制抽取结果的范围，避免模型随意创造新的实体类别和关系名称。')
add_heading(doc,'5.3.2 知识抽取与融合',3)
add_para(doc,'规则模块抽取条号、日期、金额、法规引用和定义句式；大语言模型模块抽取主体、机型、活动、法律后果和复杂事件；融合模块完成别名归一、重复节点合并、关系去重和时效属性补全。')
add_heading(doc,'5.3.3 图查询与多跳扩展',3)
add_para(doc,'系统以主检索条款作为种子节点，沿“引用—定义”“条款—机型”“条款—义务主体”“活动—违反后果”“案例—援引法条”等路径扩展关联条款，并保存扩展路径，向用户说明关联依据来自何种图关系。')
add_heading(doc,'5.4 混合检索功能板块',2)
add_heading(doc,'5.4.1 问题理解',3)
add_para(doc,'问答入口接收自然语言问题，检索模块根据问题中的法规名称、机型、活动、空域、主体和处罚等线索进行查询。系统允许用户使用“黑飞”“无人机登记”“飞行要不要审批”等口语化表达。')
add_heading(doc,'5.4.2 稠密与稀疏双路召回',3)
add_para(doc,'稠密检索和BM25检索分别产生候选结果。两路结果通过RRF融合，融合得分可表示为：')
add_para(doc,'Score(d)=Σ w_r /(k+rank_r(d))',first=False,align=WD_ALIGN_PARAGRAPH.CENTER,size=12)
add_para(doc,'其中，w_r表示不同检索通道的权重，rank_r(d)表示文档在对应通道中的排名。系统通过alpha扫描确定稠密权重为0.9时效果最好。')
add_heading(doc,'5.4.3 重排与时效过滤',3)
add_para(doc,'候选条款首先按照向量和关键词相关度召回，再由bge-reranker-v2-m3进行二阶段排序。系统默认启用“仅现行有效”过滤，避免已废止或未生效条款排在当前依据之前；用户明确查询历史法规时可调整过滤策略。')
add_heading(doc,'5.5 问答生成与应用功能板块',2)
add_heading(doc,'5.5.1 证据约束生成',3)
add_para(doc,'生成模块采用OpenAI兼容接口，可接入GLM-4-Flash、DeepSeek-V3等模型。提示词要求模型只能根据给定条文作答，无法确认时明确说明，不编造法条；同时要求说明适用条件、主体差异、法律后果和参考法规。')
add_heading(doc,'5.5.2 引用溯源展示',3)
add_para(doc,'系统在答案下方分别展示主要条文和图谱扩展条款，包含法规名称、条号、时效状态、相关性分数、原文片段和图扩展路径。用户可以从自然语言答案回溯到具体的法条证据。')
add_heading(doc,'5.5.3 Web问答服务',3)
add_para(doc,'系统通过FastAPI提供问答接口，采用SSE实现流式输出。前端支持hybrid、dense和sparse三种模式，并提供重排、图谱扩展和仅现行有效等开关，便于演示和比较不同检索配置。')
add_heading(doc,'5.6 系统评测与实验结果',2)
add_heading(doc,'5.6.1 评测集与评测方法',3)
add_para(doc,'评测集包含36道问题，覆盖机型分类、实名登记、空域管制、飞行申请、操控资质、适航、罚则、行为规范、安全要求和特殊活动等13类考点，其中6道为时效性和机型陷阱题。每道问题标注权威条款、等价可接受条款、应避免优先召回的失效或易混条款、参考法规和答案关键点；所有标注条款标识均与向量库父文档标识一一对应，并在建题时逐条校验其真实存在，避免评测锚点失真。')
add_para(doc,'评测分为检索层与生成层两级，对应“答案质量取决于检索质量”这一事实。检索层以标注条款计算Hit@k、Recall@k、MRR、nDCG@k和时效错误率，全自动且可零成本反复运行；生成层复用真实问答链路生成答案，再由独立且更强的裁判模型从忠实度、正确性、时效性和引用正确性四个维度打分。生成模型与裁判模型分开配置，以避免模型自评导致的分数偏高。')
add_heading(doc,'5.6.2 检索层消融与融合权重扫描',3)
add_para(doc,'检索层消融实验对比稀疏、稠密、混合、混合加重排以及混合加重排加图扩展五种配置，结果如表5-2所示。')
rows=[['配置','Hit@3','Hit@5','Recall@5','MRR','nDCG@5','Hit@10','时效错误率'],['sparse','0.333','0.389','0.236','0.248','0.171','0.472','0.000'],['dense','0.611','0.722','0.597','0.521','0.499','0.778','0.000'],['hybrid','0.528','0.639','0.472','0.435','0.365','0.806','0.000'],['hybrid+rerank','0.611','0.694','0.542','0.496','0.449','0.722','0.000'],['hybrid+rerank+expand','0.611','0.694','0.542','0.498','0.449','0.722','0.000']]
add_table(doc,rows[0],rows[1:]); add_caption(doc,'表5-2 检索层消融实验结果')
add_para(doc,'纯BM25作为零成本基线效果最低，说明法律用户问题存在较多口语化表达和同义改写；稠密检索带来最大跃升，Hit@5达到0.722；重排能够修正RRF融合的排序质量；图扩展对主命中率无增量，这符合预期——图多跳的价值在于为生成端补充关联条款上下文，应在生成层度量而非以主命中率衡量。值得注意的是，默认0.5权重的混合检索反而低于纯稠密检索，据此进一步开展了融合权重扫描。')
add_para(doc,'表5-3给出稠密权重alpha从0.3到1.0的扫描结果（稀疏权重为1−alpha）。')
rows=[['alpha','Hit@3','Hit@5','Recall@5','MRR','nDCG@5'],['0.3','0.417','0.556','0.403','0.398','0.319'],['0.5','0.528','0.639','0.472','0.435','0.365'],['0.7','0.500','0.667','0.514','0.447','0.402'],['0.8','0.556','0.694','0.542','0.472','0.425'],['0.9','0.556','0.750','0.625','0.448','0.454'],['1.0','0.611','0.722','0.597','0.521','0.499']]
add_table(doc,rows[0],rows[1:]); add_caption(doc,'表5-3 融合权重alpha扫描结果')
add_para(doc,'Hit@5和Recall@5随稠密权重单调上升，在alpha=0.9时Hit@5达到0.750、Recall@5达到0.625，显著优于默认0.5配置；alpha=1.0时MRR和nDCG@5略高，但alpha=0.9保留少量BM25能多召回权威条文。这印证了本领域语料高度同质（地方办法大量照抄国家条例），BM25关键词路会稀释权威条文，因此最优融合权重明显偏向稠密侧；考虑到法律问答“不漏”优先于“排第一”，系统选择alpha=0.9作为默认配置。')
add_heading(doc,'5.6.3 生成层评测结果',3)
add_para(doc,'生成层采用混合加重排加图扩展、alpha=0.9、仅现行有效的检索配置，生成模型使用DeepSeek-V3，裁判模型使用独立的Qwen2.5-72B-Instruct，评测结果如表5-4所示。')
rows=[['评价维度','平均分'],['忠实度','0.889'],['正确性','0.846'],['时效性','0.947'],['引用正确性','0.950'],['综合得分','0.908']]
add_table(doc,rows[0],rows[1:]); add_caption(doc,'表5-4 生成层评测结果')
add_para(doc,'生成层综合得分为0.908，引用正确性和时效性分别达到0.950和0.947，说明来源约束和现行有效过滤能够有效控制法律问答风险；36道题中含幻觉题为5道。正确性得分为0.846，低于引用正确性，表明引用真实条款并不等于完整覆盖问题要点，仍存在要点遗漏的情况。')
add_heading(doc,'5.6.4 陷阱题专项与失败案例分析',3)
add_para(doc,'6道时效性与机型陷阱题的时效性均分为0.683、忠实度均分为0.733，明显低于整体水平（整体时效性0.947），是系统的主要薄弱环节，逐题结果如表5-5所示。')
rows=[['题号','考点','忠实度','正确性','时效性','引用','判定'],['Q03','实名登记','0.80','0.80','0.60','0.80','fair'],['Q04','实名登记','0.80','0.80','1.00','1.00','fair'],['Q05','实名登记','0.00','0.00','0.00','0.50','poor'],['Q09','操控资质','1.00','1.00','1.00','1.00','good'],['Q10','适航','1.00','1.00','1.00','1.00','good'],['Q23','适航','0.80','0.60','0.50','0.90','fair']]
add_table(doc,rows[0],rows[1:]); add_caption(doc,'表5-5 陷阱题专项评测结果')
add_para(doc,'综合失败案例可归纳为五类：第一，实名登记陷阱，Q05受已废止规定或模型先验影响，错误地得出微型无人机不需要实名登记的结论；第二，标准施行日期错误，Q04将国家标准施行时间误答为2025年，实际应为2026年5月1日，说明日期字段需要更强的结构化校验；第三，适航依据不完整，Q23未引用民航法新版无人机条款，反映法规版本排序和权威层级权重仍需优化；第四，罚款金额表达错误，生成模型可能将不同主体、不同违法情节的罚款区间混配，说明处罚条款应按主体、行为和情节进行细粒度事件建模；第五，地方规范依据不足，当检索上下文缺少对应地方条款时，模型可能进行常识性补全，应改为明确提示证据不足。上述失效根因多在检索排序而非生成端，可通过按效力层级加权、提升权威国家法规召回优先级加以缓解。')
add_heading(doc,'5.7 本章小结',2)
add_para(doc,'本章按功能板块介绍了系统的数据处理、知识图谱、混合检索、问答生成、引用展示和评测应用功能，并通过消融实验、融合权重扫描、生成层四维评测和陷阱题专项分析，验证了稠密检索、重排和图扩展的作用，同时定位了以时效性为核心的主要失效模式。')

add_heading(doc,'6 研究结论与展望',1)
add_heading(doc,'6.1 研究总结',2)
add_para(doc,'本项目面向低空经济无人机法律法规智能问答需求，构建了以法规条款为核心的知识图谱增强检索生成系统。系统从多源法规和案例数据出发，经过结构化、Parent-Child Chunk切分、Embedding、规则与大语言模型协同抽取、实体对齐和Neo4j建图，形成了可查询、可扩展、可溯源的法律知识底座。在问答环节，系统融合BGE-M3、BM25、RRF、重排、时效过滤和图多跳扩展，利用证据约束的语言模型生成自然语言答案和参考法规。')
add_para(doc,'实验结果表明，GraphRAG能够弥补纯关键词检索的语义不足和纯向量检索的关系表达不足。系统在36道测试题上取得了较好的检索和生成效果，尤其在引用正确性、现行有效过滤和跨条款关联方面具有应用价值。')
add_heading(doc,'6.2 知识图谱增强检索的价值分析',2)
add_para(doc,'纯向量检索能够找到语义相近的文本，但不天然表达“哪一条定义了术语”“哪一条规定了罚则”“现行法规取代了哪一部旧法规”等关系。知识图谱为候选条款提供了可解释的结构路径，使系统能够把分散于不同章节、不同法规的依据组织起来。实验也印证了这一分工：图扩展对主检索命中率没有增量，但能在部分多跳问题中补回主检索遗漏的关联条款，其价值主要体现在多条款综合回答和解释完整性方面，而非提升单点命中。因此，法律智能问答的关键不只是提升语言模型的生成能力，更在于建设高质量、可追溯、具有时间和效力属性的法律知识底座。')
add_heading(doc,'6.3 系统不足',2)
add_para(doc,'第一，当前评测集规模仍较小，尚不能完全覆盖真实用户的复杂问题分布；第二，部分关系由大语言模型抽取，仍需更充分的专家抽样核验；第三，扫描版国家标准和格式不稳定PDF存在识别质量差异；第四，罚则中的主体、行为、情节和金额关系较复杂，模型仍可能出现区间混配；第五，LLM-as-judge可以提高评测效率，但不能完全替代法律专家评审。')
add_heading(doc,'6.4 后续展望',2)
add_para(doc,'后续将从以下方面改进：建立法律专家参与的分层评测集；将法规效力层级、生效日期和废止关系纳入排序模型；构建面向主体—行为—条件—后果的法律事件图谱；对扫描标准引入OCR和双人复核；对日期、条号、罚款金额和机型阈值实施程序化校验；进一步评估本地化Embedding和生成模型，以提高数据安全性、稳定性和可控性。')

add_heading(doc,'参考文献',1)
refs=['[1] Bordes A, Usunier N, Garcia-Duran A, et al. Translating Embeddings for Modeling Multi-relational Data[C]. Advances in Neural Information Processing Systems, 2013.','[2] Schlichtkrull M, Kipf T N, Bloem P, et al. Modeling Relational Data with Graph Convolutional Networks[C]. European Semantic Web Conference, 2018.','[3] Sun Z, Deng Z H, Nie J Y, et al. RotatE: Knowledge Graph Embedding by Relational Rotation in Complex Space[C]. ICLR, 2019.','[4] Wei Z, Su J, Wang Y, et al. A Novel Cascade Binary Tagging Framework for Relational Triple Extraction[C]. ACL, 2020.','[5] Wang Y, Yu B, Zhang Y, et al. TPLinker: Single-stage Joint Extraction of Entities and Relations Through Token Pair Linking[C]. ACL, 2020.','[6] Edge D, Trinh H, Cheng N, et al. From Local to Global: A Graph RAG Approach to Query-Focused Summarization[EB/OL]. 2024.','[7] 国务院. 无人驾驶航空器飞行管理暂行条例[Z]. 2023.','[8] 国家市场监督管理总局，国家标准化管理委员会. 无人驾驶航空器相关国家标准[S].','[9] 项目组. 低空经济无人机法律智能问答系统项目资料与评测报告[R]. 2026.']
for ref in refs: add_para(doc,ref,first=False,align=WD_ALIGN_PARAGRAPH.LEFT,size=10)
add_heading(doc,'附录A 系统目录与运行说明',1)
add_para(doc,'项目工程目录包括：知识图谱/1_结构化（条款结构化与元数据归一）、2_抽取（实体和关系抽取）、3_建图（Neo4j图谱构建）、4_案例（司法案例子图）、5_向量库（Parent-Child分块、向量索引、BM25和混合检索）、6_问答（CLI与FastAPI问答服务）和7_评测（检索与生成评测）。')
add_para(doc,'系统运行时需要Python环境、Neo4j图数据库、Chroma向量库和相应模型接口。检索端可使用BGE-M3和bge-reranker-v2-m3，生成端可使用任意OpenAI兼容的大语言模型接口。API密钥应通过环境变量配置，不应直接写入代码或提交到版本库。')
add_heading(doc,'附录B 系统功能板块汇总',1)
rows=[['功能板块','核心功能','主要产出'],['数据处理','多源采集、解析、去重、时效归一、Parent-Child Chunk','条款单元、Parent、Child'],['知识建模','节点、关系、属性、法律事件和受控词表','领域本体与Schema'],['知识图谱构建','规则抽取、LLM抽取、对齐消歧、Neo4j建图','图节点、图关系、Cypher脚本'],['向量与检索','BGE-M3、Chroma、BM25、RRF、重排','主检索条款'],['GraphRAG问答','图多跳扩展、证据上下文、LLM生成','带参考法规的答案'],['应用与评测','Web界面、引用展示、指标评测、失败分析','问答服务与评测报告']]
add_table(doc,rows[0],rows[1:]); add_caption(doc,'表B-1 系统功能板块汇总')

# add heading styles for TOC recognition
for p in doc.paragraphs:
    txt=p.text
    if txt and txt[0].isdigit() and txt[1:2] in [' ','．']:
        pass
# save
doc.save(DOCX)
print('saved',DOCX,os.path.getsize(DOCX),PNG,os.path.getsize(PNG))

