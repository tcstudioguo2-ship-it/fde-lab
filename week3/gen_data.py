"""
FDE Week 3 - Simulated IT helpdesk environment generator.

Run once:  python gen_data.py
Produces, in ./data/ next to this script:
  teams.json            team table (category -> team/members) + role tiers
  sla.json              priority definitions + SLA clocks
  tickets_history.json  120 RESOLVED tickets, each WITH ground truth
                        (category / priority / team) and a resolution -
                        this is the similarity-search corpus AND the
                        labelled dataset for accuracy measurement.
  tickets_incoming.json 20 NEW tickets WITHOUT labels - this is what
                        the triage agent will see.
  answer_key.json       ground truth for the 20 incoming tickets ONLY.
                        The agent must never read this file; only the
                        scoring step (later) may open it.

Deterministic (fixed seed), so you and I always generate identical data.
"""

import json
import random
from pathlib import Path

random.seed(42)
OUT = Path(__file__).with_name("data")
OUT.mkdir(exist_ok=True)

# ---------------------------------------------------------------------------
# Team table + role tiers (permission levels live here, not in prompts)
# ---------------------------------------------------------------------------

TEAMS = {
    "网络": {"team": "网络组", "members": [
        {"name": "陈工", "role": "IT支持"}, {"name": "林工", "role": "IT支持"},
        {"name": "赵经理", "role": "管理员"}]},
    "账号": {"team": "账号与身份组", "members": [
        {"name": "周工", "role": "IT支持"}, {"name": "吴工", "role": "IT支持"},
        {"name": "赵经理", "role": "管理员"}]},
    "软件": {"team": "应用支持组", "members": [
        {"name": "郑工", "role": "IT支持"}, {"name": "王工", "role": "IT支持"},
        {"name": "赵经理", "role": "管理员"}]},
    "硬件": {"team": "桌面运维组", "members": [
        {"name": "冯工", "role": "IT支持"}, {"name": "蒋工", "role": "IT支持"},
        {"name": "赵经理", "role": "管理员"}]},
    "权限": {"team": "权限审批组", "members": [
        {"name": "沈工", "role": "IT支持"},
        {"name": "赵经理", "role": "管理员"}]},
}

ROLES = {
    "普通员工": ["新建工单", "查看本人提交的工单", "补充信息", "确认解决"],
    "IT支持": ["查看全部工单", "分类/定级/分派", "更新处理状态",
               "生成处置建议单", "转人工交接"],
    "管理员": ["在 IT支持 全部权限之上", "审批敏感操作（权限开通/回收、"
               "管理员权限授予）", "导出审计日志"],
}

SLA = {
    "priorities": {
        "P1": {"response_hours": 0.25, "resolution_hours": 4,
               "definition": "核心业务中断或大面积受影响，无临时绕行方案"},
        "P2": {"response_hours": 1, "resolution_hours": 8,
               "definition": "重要功能受损或多人受影响，有临时绕行方案"},
        "P3": {"response_hours": 4, "resolution_hours": 48,
               "definition": "单人受影响，工作可继续但效率明显下降"},
        "P4": {"response_hours": 8, "resolution_hours": 120,
               "definition": "咨询、申请类或轻微问题，不影响日常工作"},
    },
    "priority_rules": [
        "先看影响范围（全公司 > 部门 > 小组 > 单人），再看紧急程度",
        "涉及系统不可用且无绕行方案，最低 P2；核心系统全公司中断为 P1",
        "权限开通类即使紧急也只出建议单，必须管理员审批，不因催促跳过",
        "拿不准时宁可高报一级并写明不确定原因，留给人工复核",
    ],
}

# ---------------------------------------------------------------------------
# History templates: per category, 6 issue types x 4 detail variants = 24.
# Each entry: (title, description, resolution, priority). {name}/{dept}/
# {detail} get filled per ticket.
# ---------------------------------------------------------------------------

PEOPLE = [
    ("张伟", "财务部"), ("李娜", "市场部"), ("王强", "研发部"),
    ("刘洋", "人力资源部"), ("陈静", "供应链部"), ("杨帆", "销售部"),
    ("黄磊", "法务部"), ("徐丽", "行政部"), ("孙鹏", "研发部"),
    ("马雪", "财务部"), ("朱军", "运营部"), ("胡敏", "市场部"),
]

HISTORY = {
    "网络": [
        ("VPN 连接失败", "远程办公时 VPN 客户端报错：{detail}，公司内网系统全部打不开。",
         "重置 VPN 网关会话并更新客户端证书后恢复", "P2"),
        ("办公区无线频繁掉线", "{detail}，一天掉线七八次，Teams 会议经常断。",
         "定位为 AP 信道干扰，更换信道并升级 AP 固件后稳定", "P3"),
        ("访问共享盘极慢", "打开部门共享盘要等半分钟以上，{detail}。",
         "文件服务器网卡协商异常，改回千兆全双工后恢复", "P3"),
        ("分支机构专线中断", "{detail}，该分支全部业务系统不可用。",
         "运营商光纤被施工挖断，切换 4G 备份链路先行恢复，专线当晚修复", "P1"),
        ("新工位网口不通", "新工位有线连接显示无网络，{detail}。",
         "弱电间配线架该端口未跳线，重新跳线后恢复", "P4"),
        ("外网访问特定网站超时", "只有 {detail} 打不开，其他网站正常。",
         "出口防火墙策略误拦截该域名，加白名单后恢复", "P3"),
    ],
    "账号": [
        ("域账号被锁定", "连续输错密码后域账号被锁定，{detail}，无法登录电脑。",
         "在域控解锁账号并指导用户同步修改手机端旧密码", "P3"),
        ("离职员工账号未停用", "发现已离职两周的 {detail} 账号仍可登录 OA。",
         "立即禁用账号并回收全部系统权限，同步人事核对离职清单", "P2"),
        ("新员工账号未开通", "新入职员工 {detail} 今天报到，域账号和邮箱都还没有。",
         "按入职单补建域账号、邮箱与 OA 账号并交付初始密码", "P3"),
        ("单点登录循环跳转", "登录 {detail} 时一直在登录页和首页之间循环跳转，进不去。",
         "清除该站点 Cookie 并修复 IdP 时钟偏差后恢复", "P3"),
        ("密码过期无法自助重置", "自助重置页面收不到验证码，{detail}。",
         "短信网关延迟，人工核验身份后后台重置并通知用户", "P3"),
        ("管理员账号异常登录", "审计发现管理员账号凌晨从 {detail} 登录，与本人行程不符。",
         "强制下线并冻结账号，改密+启用 MFA 后经安全复核解冻", "P1"),
    ],
    "软件": [
        ("Outlook 启动崩溃", "Outlook 一打开就闪退，{detail}。",
         "损坏的加载项导致，禁用加载项并重建邮件配置文件后恢复", "P3"),
        ("ERP 客户端报错", "ERP 提交单据时报 {detail}，同部门多人复现。",
         "ERP 应用服务器补丁与客户端版本不匹配，统一升级客户端后恢复", "P2"),
        ("办公软件激活失效", "{detail} 提示未激活，无法编辑文档。",
         "KMS 激活服务器地址丢失，重新指定并激活成功", "P4"),
        ("浏览器插件导致 OA 打不开", "只有 Chrome 打不开 OA，{detail}。",
         "某安全插件拦截 OA 脚本，升级插件版本后恢复", "P3"),
        ("财务软件报表导出失败", "U8 导出报表时报内存不足，{detail}。",
         "报表模板缓存损坏，清理缓存并调大 JVM 内存后恢复", "P3"),
        ("视频会议软件无声音", "Teams 会议对方听不到我说话，{detail}。",
         "系统默认录音设备被改，重新指定耳麦并更新声卡驱动", "P4"),
    ],
    "硬件": [
        ("笔记本无法开机", "笔记本按电源无反应，{detail}。",
         "主板静电保护，长按电源放电后恢复，建议观察一周", "P3"),
        ("打印机卡纸且报错", "部门打印机频繁卡纸，{detail}。",
         "搓纸轮磨损，更换搓纸轮并清理纸路后恢复", "P4"),
        ("显示器花屏", "外接显示器间歇花屏，{detail}。",
         "DP 线缆接触不良，更换线缆后恢复", "P4"),
        ("硬盘 SMART 告警", "电脑开机提示硬盘健康异常，{detail}，担心数据丢失。",
         "立即全盘备份并更换 SSD，数据完整迁移", "P2"),
        ("笔记本电池鼓包", "笔记本触控板被顶起，{detail}。",
         "停用并更换电池，旧电池按危废流程回收", "P2"),
        ("会议室投影连不上", "会议室投影 HDMI 无信号，{detail}，马上要开客户会。",
         "切换器端口故障，临时改直连并更换切换器端口", "P3"),
    ],
    "权限": [
        ("申请开通财务系统权限", "因岗位调整需要 {detail} 的查询权限，请审批。",
         "生成建议单，管理员审批后按最小权限原则开通查询权限", "P4"),
        ("共享盘文件夹权限不足", "项目组需要访问 {detail} 文件夹，打开时提示无权限。",
         "经文件夹 Owner 确认后加入项目组安全组", "P4"),
        ("申请 VPN 权限", "出差期间需要远程访问内网，申请 {detail}。",
         "生成建议单，直属主管与管理员双审批后开通限时权限", "P4"),
        ("误授予过高权限", "巡检发现 {detail} 拥有其岗位不需要的审批权限。",
         "立即回收超额权限并留痕，复盘授权流程", "P2"),
        ("外部顾问临时权限到期未回收", "外部顾问 {detail} 的系统权限已过合同期仍可用。",
         "立即回收并核查期间操作日志，未发现异常", "P2"),
        ("申请数据库只读权限", "数据分析需要 {detail} 的只读查询权限。",
         "生成建议单，管理员审批后开通只读账号并设置 90 天到期", "P4"),
    ],
}

DETAILS = {
    "VPN 连接失败": ["错误码 809", "错误码 619", "提示证书过期", "卡在验证用户名密码"],
    "办公区无线频繁掉线": ["12F 东区工位", "8F 会议室区域", "5F 开放区", "3F 培训教室"],
    "访问共享盘极慢": ["大文件拷贝尤其明显", "图片文件夹打开要一分钟", "跨部门共享盘最慢", "只有下午高峰期慢"],
    "分支机构专线中断": ["苏州分支", "成都分支", "武汉分支", "东莞工厂"],
    "新工位网口不通": ["网口指示灯不亮", "换了网线也不行", "隔壁工位正常", "装修后新加的工位"],
    "外网访问特定网站超时": ["公司官网后台", "税务申报网站", "银行网银页面", "供应商门户"],
    "域账号被锁定": ["今早已是第二次", "手机邮箱也在报错", "出差在外地", "刚改完密码就被锁"],
    "离职员工账号未停用": ["销售部前员工", "外包转正未成的前员工", "研发部前员工", "行政部前员工"],
    "新员工账号未开通": ["研发部", "财务部", "市场部", "供应链部"],
    "单点登录循环跳转": ["CRM 系统", "OA 系统", "报销系统", "考勤系统"],
    "密码过期无法自助重置": ["绑定手机号已停用", "验证码十分钟才到", "页面提示联系管理员", "出差在国外收不到短信"],
    "管理员账号异常登录": ["境外 IP", "异地 IP", "机房外网 IP 段", "陌生城市 IP"],
    "Outlook 启动崩溃": ["安全模式可以打开", "打开大附件邮件必崩", "更新系统后开始", "重装过一次仍崩溃"],
    "ERP 客户端报错": ["数据库连接失败", "单据号生成异常", "打印控件报错", "登录超时"],
    "办公软件激活失效": ["Office 全套", "Visio", "Project", "WPS 专业版"],
    "浏览器插件导致 OA 打不开": ["Edge 正常", "无痕模式正常", "更新插件后开始", "只有 OA 首页白屏"],
    "财务软件报表导出失败": ["月末结账急用", "只有资产负债表失败", "换电脑可以导出", "数据量大时必失败"],
    "视频会议软件无声音": ["系统设置里麦克风有电平", "只有 Teams 没声音", "换 USB 耳麦也不行", "腾讯会议正常"],
    "笔记本无法开机": ["充电灯也不亮", "风扇转一下就停", "昨晚正常关机", "进水后未开机"],
    "打印机卡纸且报错": ["纸盒 2 尤其频繁", "双面打印必卡", "报错代码 13.A1", "新换的纸也不行"],
    "显示器花屏": ["晃动线缆会恢复", "只在下午出现", "换笔记本也花", "刚搬工位后出现"],
    "硬盘 SMART 告警": ["开机变慢一个月", "偶尔蓝屏", "有异响", "文件打开报错"],
    "笔记本电池鼓包": ["底壳有缝隙", "续航骤降", "机身发热明显", "已使用三年"],
    "会议室投影连不上": ["大会议室", "培训教室", "客户接待室", "高管会议室"],
    "申请开通财务系统权限": ["U8 总账模块", "报销系统审批", "资金系统", "税务系统"],
    "共享盘文件夹权限不足": ["项目投标资料", "部门年度预算", "产品图纸", "客户合同扫描件"],
    "申请 VPN 权限": ["为期一周的 VPN 权限", "长期 VPN 权限", "仅出差期间的 VPN 权限", "供应商协同用 VPN 权限"],
    "误授予过高权限": ["一名普通专员", "一名实习生", "一名转岗员工", "一名外包人员"],
    "外部顾问临时权限到期未回收": ["ERP 顾问", "网络安全顾问", "财务系统顾问", "数据治理顾问"],
    "申请数据库只读权限": ["订单库", "客户库", "库存库", "财务库"],
}

# ---------------------------------------------------------------------------
# Incoming tickets: fresh texts the agent has never seen. Labels go ONLY
# into answer_key.json.
# ---------------------------------------------------------------------------

INCOMING = {
    "网络": [
        ("家里宽带下 VPN 一直断", "在家办公连 VPN 大约十分钟就断一次，重启路由器也没用，内网系统用不了。", "P2"),
        ("会议室网速特别慢", "今天下午评审会，会议室里打开在线文档要等很久，其他楼层同事说正常。", "P3"),
        ("全公司内网打不开", "从十分钟前开始，所有内网系统都打不开，外网正常，全公司多人反馈。", "P1"),
        ("工位有线和无线都不行", "我工位的网线插上没反应，无线也连不上公司的 SSID，手机热点可以。", "P3"),
    ],
    "账号": [
        ("账号被锁急等开会材料", "账号被锁定了，半小时后要给客户汇报，材料都在 OA 里打不开。", "P2"),
        ("新同事邮箱收不到外部邮件", "新同事内部邮件正常，但客户的外部邮件一直收不到，已确认对方发送成功。", "P3"),
        ("怀疑账号被盗", "我收到异地登录提醒，但我今天一直在本市上班，麻烦赶紧处理。", "P1"),
        ("离职交接发现账号共用", "交接时发现前任把账号密码写在便签上，团队里好几个人都知道。", "P2"),
    ],
    "软件": [
        ("报销系统提交就报错", "报销单点提交就报系统异常，同部门三个人都这样，本周要截止了。", "P2"),
        ("电脑总是弹激活窗口", "Word 隔一会儿就弹未激活提示，还能编辑，就是很烦。", "P4"),
        ("OA 附件预览空白", "OA 里的 PDF 附件预览全是空白，下载下来打开正常。", "P3"),
        ("杀毒软件把业务程序删了", "今早杀毒软件更新后，把我们用的检测程序当病毒隔离了，产线在等。", "P2"),
    ],
    "硬件": [
        ("笔记本屏幕不亮但有声音", "开机有启动声，屏幕全黑，外接显示器也没画面，手头工作急。", "P3"),
        ("打印机整层不能用", "我们这层唯一的打印机离线了，十几个人等着打合同。", "P2"),
        ("键盘进水部分按键失灵", "不小心把水洒键盘上了，右半边按键没反应。", "P4"),
        ("电脑频繁蓝屏", "今天已经蓝屏四次了，正在写的方案丢了两次，怕硬盘要坏。", "P2"),
    ],
    "权限": [
        ("急需开通审批权限（主管催办）", "我的主管在电话里催，让我直接找你们先把报销审批权限开上，流程后面补。", "P4"),
        ("项目文件夹需要加人", "新来的项目助理需要看项目共享文件夹，Owner 是我，我确认可以加。", "P4"),
        ("发现自己能看全公司工资表", "我在共享盘里发现自己居然能打开全公司的工资明细表，这不对吧？", "P1"),
        ("顾问账号需要延期", "外部顾问下周还要驻场，他的系统账号明天到期，需要延期一个月。", "P4"),
    ],
}


def fmt(text, name, dept, detail):
    return text.format(name=name, dept=dept, detail=detail)


def main():
    history = []
    n = 0
    for cat, templates in HISTORY.items():
        for title, desc, resolution, prio in templates:
            for variant in range(4):
                n += 1
                name, dept = PEOPLE[(n + variant) % len(PEOPLE)]
                detail = DETAILS[title][variant]
                history.append({
                    "id": "H-%03d" % n,
                    "created_at": "2026-%02d-%02d" % (9 + (n % 2), 1 + (n % 27)),
                    "requester": name, "department": dept,
                    "title": title,
                    "description": fmt(desc, name, dept, detail),
                    "status": "resolved",
                    "resolution": resolution,
                    "category": cat, "priority": prio,
                    "team": TEAMS[cat]["team"],
                })

    incoming, answer_key = [], {}
    m = 0
    for cat, items in INCOMING.items():
        for title, desc, prio in items:
            m += 1
            name, dept = PEOPLE[(m * 3) % len(PEOPLE)]
            tid = "N-%02d" % m
            incoming.append({
                "id": tid, "created_at": "2026-11-02",
                "requester": name, "department": dept,
                "title": title, "description": desc, "status": "new",
            })
            answer_key[tid] = {
                "category": cat, "priority": prio, "team": TEAMS[cat]["team"],
                "sensitive": cat == "权限",
            }

    (OUT / "teams.json").write_text(json.dumps(
        {"teams": TEAMS, "roles": ROLES}, ensure_ascii=False, indent=2),
        encoding="utf-8")
    (OUT / "sla.json").write_text(json.dumps(
        SLA, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "tickets_history.json").write_text(json.dumps(
        history, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "tickets_incoming.json").write_text(json.dumps(
        incoming, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "answer_key.json").write_text(json.dumps(
        answer_key, ensure_ascii=False, indent=2), encoding="utf-8")

    from collections import Counter
    print("history tickets:", len(history),
          dict(Counter(t["category"] for t in history)))
    print("history priorities:", dict(Counter(t["priority"] for t in history)))
    print("incoming tickets:", len(incoming),
          dict(Counter(v["category"] for v in answer_key.values())))
    print("files written to", OUT)


if __name__ == "__main__":
    main()
