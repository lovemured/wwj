from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor


OUTPUT = "/Users/mured/wwj/wwjapi/徐弘-测试工程师-优化版.docx"
EAST_ASIA_FONT = "PingFang SC"
LATIN_FONT = "Arial"


def set_run_font(run, size=9.5, bold=False, color="333333"):
    run.font.name = LATIN_FONT
    run._element.get_or_add_rPr().rFonts.set(qn("w:ascii"), LATIN_FONT)
    run._element.get_or_add_rPr().rFonts.set(qn("w:hAnsi"), LATIN_FONT)
    run._element.get_or_add_rPr().rFonts.set(qn("w:eastAsia"), EAST_ASIA_FONT)
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = RGBColor.from_string(color)


def set_paragraph(paragraph, before=0, after=0, line=1.0, keep=False):
    fmt = paragraph.paragraph_format
    fmt.space_before = Pt(before)
    fmt.space_after = Pt(after)
    fmt.line_spacing = line
    fmt.keep_with_next = keep


def add_text(paragraph, text, size=9.5, bold=False, color="333333"):
    run = paragraph.add_run(text)
    set_run_font(run, size=size, bold=bold, color=color)
    return run


def set_bottom_border(paragraph, color="C7D0D5", size="5", space="4"):
    p_pr = paragraph._p.get_or_add_pPr()
    p_borders = p_pr.find(qn("w:pBdr"))
    if p_borders is None:
        p_borders = OxmlElement("w:pBdr")
        p_pr.append(p_borders)
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), size)
    bottom.set(qn("w:space"), space)
    bottom.set(qn("w:color"), color)
    p_borders.append(bottom)


def add_section_heading(doc, text):
    p = doc.add_paragraph()
    set_paragraph(p, before=7, after=3, line=1.0, keep=True)
    add_text(p, text, size=11.5, bold=True, color="111111")
    set_bottom_border(p)
    return p


def add_bullet(doc, text, after=1.2):
    p = doc.add_paragraph()
    p.paragraph_format.left_indent = Inches(0.17)
    p.paragraph_format.first_line_indent = Inches(-0.13)
    set_paragraph(p, after=after, line=1.04)
    add_text(p, "- ", size=9.35, color="40515B")
    add_text(p, text, size=9.35, color="333333")
    return p


def add_role(doc, company, role, dates):
    p = doc.add_paragraph()
    set_paragraph(p, before=3.5, after=1.5, line=1.0, keep=True)
    add_text(p, company, size=10.4, bold=True, color="1F3A4A")
    add_text(p, "  |  " + role, size=9.5, color="444444")
    add_text(p, "  |  " + dates, size=9.3, color="666666")
    return p


def add_project(doc, title, role, dates, intro, bullets):
    add_role(doc, title, role, dates)
    p = doc.add_paragraph()
    set_paragraph(p, after=1.5, line=1.04)
    add_text(p, "项目简介：", size=9.2, bold=True, color="40515B")
    add_text(p, intro, size=9.2, color="444444")
    for bullet in bullets:
        add_bullet(doc, bullet, after=0.9)


doc = Document()
section = doc.sections[0]
section.top_margin = Inches(0.42)
section.bottom_margin = Inches(0.42)
section.left_margin = Inches(0.62)
section.right_margin = Inches(0.62)

normal = doc.styles["Normal"]
normal.font.name = LATIN_FONT
normal._element.rPr.rFonts.set(qn("w:ascii"), LATIN_FONT)
normal._element.rPr.rFonts.set(qn("w:hAnsi"), LATIN_FONT)
normal._element.rPr.rFonts.set(qn("w:eastAsia"), EAST_ASIA_FONT)
normal.font.size = Pt(9.5)
normal.paragraph_format.space_after = Pt(0)
normal.paragraph_format.line_spacing = 1.0

for style_name in ("Title", "Heading 1", "Heading 2"):
    style = doc.styles[style_name]
    style.font.name = LATIN_FONT
    style._element.rPr.rFonts.set(qn("w:ascii"), LATIN_FONT)
    style._element.rPr.rFonts.set(qn("w:hAnsi"), LATIN_FONT)
    style._element.rPr.rFonts.set(qn("w:eastAsia"), EAST_ASIA_FONT)
    style.font.color.rgb = RGBColor(17, 17, 17)

# Header
p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
set_paragraph(p, after=2, line=1.0, keep=True)
add_text(p, "徐弘", size=22, bold=True, color="111111")

p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
set_paragraph(p, after=1.5, line=1.0, keep=True)
add_text(p, "软件测试工程师  |  13年工作经验  |  上海", size=9.6, color="4B555B")

p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
set_paragraph(p, after=1.5, line=1.0, keep=True)
add_text(p, "18217038858  |  18217038858@163.com  |  期望薪资 16-17K", size=9.5, color="4B555B")

add_section_heading(doc, "职业概述")
p = doc.add_paragraph()
set_paragraph(p, after=2.5, line=1.06)
add_text(
    p,
    "13年软件测试经验，覆盖智能销售 SaaS、CRM、保险业务系统、智能语音分析与 OCR 等产品。熟悉 App、Web、接口及接口自动化测试，"
    "能够独立完成需求评审、测试设计、用例评审、测试执行、缺陷闭环、回归验证和发布验收；擅长通过抓包与接口工具协助定位问题，"
    "并结合线上工单完成问题复现和跟踪。",
    size=9.55,
)

add_section_heading(doc, "核心技能")
skills = [
    ("测试类型", "功能测试、业务流程测试、接口测试、接口自动化、集成测试、回归测试、冒烟测试、兼容性测试、异常场景测试"),
    ("测试工具", "Postman、JMeter、Charles、Fiddler、Jenkins、禅道、QC、SVN"),
    ("AI 工具", "熟悉使用 Codex、Claude 辅助需求拆解、测试点梳理、用例草稿、接口脚本生成与问题分析"),
    ("测试方法", "等价类、边界值、场景法、流程图法、风险分析、用例评审、缺陷管理、线上问题复现"),
    ("业务领域", "CRM、获客与线索管理、客户管理、电话机器人、AI 机器人智能体、保险承保与审批、OCR/语音分析"),
]
for label, content in skills:
    p = doc.add_paragraph()
    set_paragraph(p, after=0.9, line=1.03)
    add_text(p, label + "：", size=9.25, bold=True, color="1F3A4A")
    add_text(p, content, size=9.25, color="333333")

add_section_heading(doc, "工作经历")
add_role(doc, "上海微问家信息技术有限公司", "软件测试工程师", "2021.08-至今")
for text in [
    "负责励销云全流程智能销售 SaaS 平台的 App、Web 及接口测试，覆盖 CRM、搜客宝、电话机器人和 AI 机器人智能体等产品模块。",
    "参与需求评审，梳理获客、筛客、管客业务链路及跨模块交互，设计和评审测试用例，推进冒烟、集成、回归与发布验收。",
    "使用禅道提交、跟踪并闭环缺陷，结合 Postman、Charles、Fiddler 协助开发复现问题，分析接口返回、请求参数及业务原因。",
    "维护接口自动化测试平台中的模块接口和集成任务，参与测试数据准备、脚本调试及迭代后的持续执行。",
    "结合 Codex、Claude 等 AI 工具辅助拆解需求、补充测试场景、生成用例草稿和接口脚本初稿，提高测试准备效率。",
    "配合 Jenkins 完成版本发布后的验证测试，协助技术支持复现线上用户工单、提单跟踪并反馈处理结果。",
    "整理公共用例库，参与测试团队周会和经验分享，持续完善测试流程与协作规范。",
]:
    add_bullet(doc, text)

add_role(doc, "神州数码系统集成服务有限公司", "测试工程师", "2015.07-2021.07")
for text in [
    "负责太平洋保险相关 App、Web 及业务系统测试，覆盖电话销售、跨条线业务审批、智能语音分析等项目。",
    "参与需求分析、技术评审和测试计划制定，负责测试点梳理、用例编写与评审、测试执行及测试报告输出归档。",
    "依据项目准入准出标准组织冒烟、集成、回归测试，跟踪缺陷修复与版本封板，及时识别并同步项目风险。",
    "使用 QC、禅道管理缺陷，协助开发定位问题；通过 SVN 维护版本内容、测试资料及稳定用例。",
]:
    add_bullet(doc, text)

add_section_heading(doc, "项目经历")
add_project(
    doc,
    "励销云全流程智能销售 SaaS 平台",
    "测试工程师",
    "2021.08-至今",
    "面向中小企业提供从获客、筛客到管客的一体化销售管理能力，包含 CRM、搜客宝、电话机器人及 AI 机器人智能体等产品。",
    [
        "负责 CRM 客户与线索管理、搜客宝获客、电话机器人及 AI 机器人智能体的功能、接口和业务流程测试。",
        "覆盖客户/线索新增编辑、分配转移、跟进流转、筛选检索、机器人任务及智能体交互等核心场景，并关注权限、数据一致性和异常流程。",
        "参与需求评审、版本发版同步和问题闭环；在接口自动化平台维护模块接口，集成至统一任务中调试并持续执行。",
        "配合 Jenkins 完成发布验证，结合线上用户工单复现问题、提交缺陷并跟踪反馈。",
    ],
)
add_project(
    doc,
    "集团2016版智能语音分析系统",
    "测试工程师",
    "2019.01-2021.07",
    "面向本级双录、二维码双录、远程双录等渠道，提供双录检测、票据/OCR 识别、体检单信息提取、证件信息提取和保单首单质检能力。",
    [
        "参与需求评审，编写测试方案与测试用例并执行，覆盖登录、密码修改、双录事中检测、票据识别及信息提取等功能。",
        "提交并跟踪缺陷，验证修复结果，输出缺陷报告和测试报告。",
    ],
)
add_project(
    doc,
    "寿险2018版跨条线业务审批系统",
    "测试工程师",
    "2018.09-2021.03",
    "支持特殊业务线上申请、审批及按业务规则向核心系统发起数据修改，包含续期退费、通用数修、专项数修、审批查询和审批链配置等功能。",
    [
        "参与需求分析和评审，整理测试点，编写并评审测试方案及用例，执行版本测试和回归测试。",
        "跟踪缺陷并在版本封板后组织回归验证，将稳定版本内容及测试报告归档至 SVN。",
    ],
)
add_project(
    doc,
    "寿险2015版电话销售系统",
    "测试工程师",
    "2015.08-2018.08",
    "支持业务员在线录单、调用 FF 核心系统完成核保，并联动资金平台完成实时或非实时支付。",
    [
        "参与需求规格说明书和技术评审，依据业务流程设计并评审测试用例。",
        "按照项目准入准出标准执行冒烟、集成和回归测试，使用 QC 跟踪缺陷并按日报同步测试进度。",
        "针对线上问题组织复盘，分析问题复现路径和产生原因，输出后续改进措施。",
    ],
)

add_section_heading(doc, "教育经历")
for school, degree, major, dates in [
    ("南京大学网络教育学院", "本科", "信息管理与信息系统", "2018-2021"),
    ("南京机电职业技术学院", "大专", "计算机信息管理", "2008-2011"),
]:
    p = doc.add_paragraph()
    set_paragraph(p, after=1.2, line=1.0)
    add_text(p, school, size=9.5, bold=True, color="333333")
    add_text(p, "  |  " + degree + "  |  " + major + "  |  " + dates, size=9.35, color="555555")

footer = section.footer
fp = footer.paragraphs[0]
fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
set_paragraph(fp, before=1, after=0, line=1.0)
add_text(fp, "徐弘  |  软件测试工程师", size=7.6, color="8A9398")

doc.save(OUTPUT)
print(OUTPUT)
