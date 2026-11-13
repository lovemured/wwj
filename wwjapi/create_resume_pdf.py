from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    HRFlowable,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    KeepTogether,
)
from reportlab.pdfgen.canvas import Canvas


OUTPUT = "/Users/mured/Documents/hsu/徐弘-测试工程师-优化版.pdf"
FONT_PATH = "/System/Library/Fonts/Supplemental/Arial Unicode.ttf"
FONT = "ResumeUnicode"

pdfmetrics.registerFont(TTFont(FONT, FONT_PATH))

PAGE_W, PAGE_H = A4
MARGIN_X = 17 * mm
TOP = 13 * mm
BOTTOM = 13 * mm
CONTENT_W = PAGE_W - 2 * MARGIN_X

INK = colors.HexColor("#242B30")
MUTED = colors.HexColor("#59656D")
ACCENT = colors.HexColor("#1F4E5F")
RULE = colors.HexColor("#C8D1D5")


styles = getSampleStyleSheet()
styles.add(
    ParagraphStyle(
        name="ResumeName",
        parent=styles["Normal"],
        fontName=FONT,
        fontSize=24,
        leading=28,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#111111"),
        spaceAfter=2,
    )
)
styles.add(
    ParagraphStyle(
        name="ResumeContact",
        parent=styles["Normal"],
        fontName=FONT,
        fontSize=9.2,
        leading=14,
        alignment=TA_CENTER,
        textColor=MUTED,
        spaceAfter=0,
    )
)
styles.add(
    ParagraphStyle(
        name="Section",
        parent=styles["Normal"],
        fontName=FONT,
        fontSize=12.2,
        leading=15,
        textColor=colors.HexColor("#111111"),
        spaceBefore=7,
        spaceAfter=3,
        keepWithNext=True,
    )
)
styles.add(
    ParagraphStyle(
        name="Body",
        parent=styles["Normal"],
        fontName=FONT,
        fontSize=9.25,
        leading=14,
        textColor=INK,
        spaceAfter=3,
    )
)
styles.add(
    ParagraphStyle(
        name="Skill",
        parent=styles["Normal"],
        fontName=FONT,
        fontSize=9.1,
        leading=13.2,
        textColor=INK,
        spaceAfter=2,
    )
)
styles.add(
    ParagraphStyle(
        name="Role",
        parent=styles["Normal"],
        fontName=FONT,
        fontSize=10.2,
        leading=13,
        textColor=ACCENT,
        spaceBefore=5,
        spaceAfter=1,
        keepWithNext=True,
    )
)
styles.add(
    ParagraphStyle(
        name="RoleMeta",
        parent=styles["Normal"],
        fontName=FONT,
        fontSize=9.1,
        leading=13,
        textColor=MUTED,
        spaceAfter=2,
        keepWithNext=True,
    )
)
styles.add(
    ParagraphStyle(
        name="ResumeBullet",
        parent=styles["Normal"],
        fontName=FONT,
        fontSize=9.05,
        leading=13.3,
        leftIndent=11,
        firstLineIndent=-9,
        textColor=INK,
        spaceAfter=1.5,
    )
)
styles.add(
    ParagraphStyle(
        name="ProjectIntro",
        parent=styles["Normal"],
        fontName=FONT,
        fontSize=9.0,
        leading=13.2,
        textColor=colors.HexColor("#465158"),
        spaceAfter=2,
    )
)
styles.add(
    ParagraphStyle(
        name="Education",
        parent=styles["Normal"],
        fontName=FONT,
        fontSize=9.2,
        leading=13.5,
        textColor=INK,
        spaceAfter=2,
    )
)


def p(text, style="Body"):
    return Paragraph(text, styles[style])


def section_heading(text):
    return [
        Paragraph(text, styles["Section"]),
        HRFlowable(width="100%", thickness=0.55, color=RULE, spaceBefore=0, spaceAfter=5),
    ]


def bullet(text):
    return Paragraph("- " + text, styles["ResumeBullet"])


def role_header(company, role, dates):
    return [
        p(f"<b>{company}</b>", "Role"),
        p(f"{role}  |  {dates}", "RoleMeta"),
    ]


def project(title, role, dates, intro, bullets):
    flow = role_header(title, role, dates)
    flow.append(p(f"<b>项目简介：</b>{intro}", "ProjectIntro"))
    flow.extend(bullet(item) for item in bullets)
    return KeepTogether(flow)


def draw_footer(canvas: Canvas, doc):
    canvas.saveState()
    canvas.setFont(FONT, 7.5)
    canvas.setFillColor(colors.HexColor("#8A9398"))
    canvas.drawCentredString(PAGE_W / 2, 8 * mm, f"徐弘  |  软件测试工程师  |  {doc.page}")
    canvas.restoreState()


doc = BaseDocTemplate(
    OUTPUT,
    pagesize=A4,
    leftMargin=MARGIN_X,
    rightMargin=MARGIN_X,
    topMargin=TOP,
    bottomMargin=BOTTOM,
    title="徐弘 软件测试工程师 简历",
    author="徐弘",
)
frame = Frame(
    MARGIN_X,
    BOTTOM + 4 * mm,
    CONTENT_W,
    PAGE_H - TOP - BOTTOM - 4 * mm,
    id="resume",
)
doc.addPageTemplates([PageTemplate(id="resume", frames=[frame], onPage=draw_footer)])

story = [
    p("徐弘", "ResumeName"),
    p("软件测试工程师  |  13年工作经验  |  上海", "ResumeContact"),
    p("18217038858  |  18217038858@163.com  |  期望薪资 16-17K", "ResumeContact"),
    Spacer(1, 4),
]

story.extend(section_heading("职业概述"))
story.append(
    p(
        "13年软件测试经验，覆盖智能销售 SaaS、CRM、保险业务系统、智能语音分析与 OCR 等产品。"
        "熟悉 App、Web、接口及接口自动化测试，能够独立完成需求评审、测试设计、用例评审、"
        "测试执行、缺陷闭环、回归验证和发布验收；擅长通过抓包与接口工具协助定位问题，"
        "并结合线上工单完成问题复现和跟踪。"
    )
)

story.extend(section_heading("核心技能"))
for label, content in [
    ("测试类型", "功能测试、业务流程测试、接口测试、接口自动化、集成测试、回归测试、冒烟测试、兼容性测试、异常场景测试"),
    ("测试工具", "Postman、JMeter、Charles、Fiddler、Jenkins、禅道、QC、SVN"),
    ("AI 工具", "熟悉使用 Codex、Claude 辅助需求拆解、测试点梳理、用例草稿、接口脚本生成与问题分析"),
    ("测试方法", "等价类、边界值、场景法、流程图法、风险分析、用例评审、缺陷管理、线上问题复现"),
    ("业务领域", "CRM、获客与线索管理、客户管理、电话机器人、AI 机器人智能体、保险承保与审批、OCR/语音分析"),
]:
    story.append(p(f"<b>{label}：</b>{content}", "Skill"))

story.extend(section_heading("工作经历"))
story.extend(
    role_header("上海微问家信息技术有限公司", "软件测试工程师", "2021.08-至今")
)
for text in [
    "负责励销云全流程智能销售 SaaS 平台的 App、Web 及接口测试，覆盖 CRM、搜客宝、电话机器人和 AI 机器人智能体等产品模块。",
    "参与需求评审，梳理获客、筛客、管客业务链路及跨模块交互，设计和评审测试用例，推进冒烟、集成、回归与发布验收。",
    "使用禅道提交、跟踪并闭环缺陷，结合 Postman、Charles、Fiddler 协助开发复现问题，分析接口返回、请求参数及业务原因。",
    "维护接口自动化测试平台中的模块接口和集成任务，参与测试数据准备、脚本调试及迭代后的持续执行。",
    "结合 Codex、Claude 等 AI 工具辅助拆解需求、补充测试场景、生成用例草稿和接口脚本初稿，提高测试准备效率。",
    "配合 Jenkins 完成版本发布后的验证测试，协助技术支持复现线上用户工单、提单跟踪并反馈处理结果。",
    "整理公共用例库，参与测试团队周会和经验分享，持续完善测试流程与协作规范。",
]:
    story.append(bullet(text))

story.extend(role_header("神州数码系统集成服务有限公司", "测试工程师", "2015.07-2021.07"))
for text in [
    "负责太平洋保险相关 App、Web 及业务系统测试，覆盖电话销售、跨条线业务审批、智能语音分析等项目。",
    "参与需求分析、技术评审和测试计划制定，负责测试点梳理、用例编写与评审、测试执行及测试报告输出归档。",
    "依据项目准入准出标准组织冒烟、集成、回归测试，跟踪缺陷修复与版本封板，及时识别并同步项目风险。",
    "使用 QC、禅道管理缺陷，协助开发定位问题；通过 SVN 维护版本内容、测试资料及稳定用例。",
]:
    story.append(bullet(text))

story.extend(section_heading("项目经历"))
story.append(
    project(
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
)

story.append(PageBreak())
story.extend(section_heading("项目经历"))
story.append(
    project(
        "集团2016版智能语音分析系统",
        "测试工程师",
        "2019.01-2021.07",
        "面向本级双录、二维码双录、远程双录等渠道，提供双录检测、票据/OCR 识别、体检单信息提取、证件信息提取和保单首单质检能力。",
        [
            "参与需求评审，编写测试方案与测试用例并执行，覆盖登录、密码修改、双录事中检测、票据识别及信息提取等功能。",
            "提交并跟踪缺陷，验证修复结果，输出缺陷报告和测试报告。",
        ],
    )
)
story.append(
    project(
        "寿险2018版跨条线业务审批系统",
        "测试工程师",
        "2018.09-2021.03",
        "支持特殊业务线上申请、审批及按业务规则向核心系统发起数据修改，包含续期退费、通用数修、专项数修、审批查询和审批链配置等功能。",
        [
            "参与需求分析和评审，整理测试点，编写并评审测试方案及用例，执行版本测试和回归测试。",
            "跟踪缺陷并在版本封板后组织回归验证，将稳定版本内容及测试报告归档至 SVN。",
        ],
    )
)
story.append(
    project(
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
)

story.extend(section_heading("教育经历"))
for school, degree, major, dates in [
    ("南京大学网络教育学院", "本科", "信息管理与信息系统", "2018-2021"),
    ("南京机电职业技术学院", "大专", "计算机信息管理", "2008-2011"),
]:
    story.append(
        p(f"<b>{school}</b>  |  {degree}  |  {major}  |  {dates}", "Education")
    )

doc.build(story)
print(OUTPUT)
