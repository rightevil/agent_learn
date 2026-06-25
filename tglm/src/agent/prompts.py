"""Agent 各节点的 prompt 模板"""
from __future__ import annotations

from datetime import date


INTAKE_PROMPT = """你是一个旅行规划助手。请从用户的输入中抽取以下信息，能抽多少抽多少，不要编造。任何不确定的字段都留空。

【重要】所有字段值必须是简单字符串或 null，不要返回嵌套对象！
正确示例：{{"origin": "杭州东"}}
错误示例：{{"origin": {{"raw_text": "杭州东"}}}}

需要抽取的字段：
- origin: 出发地（如 "杭州电子科技大学研究生公寓"），没有就填 null
- destination: 目的地（如 "宁波东钱湖"），没有就填 null
- date: 出发日期（YYYY-MM-DD 格式；若用户说"这周六"需结合今天日期换算；如果用户没说就填 null）
- earliest_time: 最早可出门时间（HH:MM 24小时制；用户没说就填 null）
- return_required: 是否需要回程（true/false；用户没说就填 null）
- play_duration_hours: 预计游玩小时数（整数；用户没说就填 null）

今天的日期是 {today}。

用户输入：
\"\"\"{user_message}\"\"\"

请以纯 JSON 输出，不要带 markdown 代码块标记，schema 如下：
{{
  "origin": null | "string",
  "destination": null | "string",
  "date": null | "YYYY-MM-DD",
  "earliest_time": null | "HH:MM",
  "return_required": null | true | false,
  "play_duration_hours": null | int
}}
"""


SLOT_UPDATE_PROMPT = """用户在回答你的追问，请把他的回答更新到已有的意图字段中，仅返回被更新的字段（增量更新，没提到的字段不要返回）。

【重要】origin 和 destination 字段值必须是简单字符串，不要返回嵌套对象！
正确示例：{{"origin": "杭州东"}}
错误示例：{{"origin": {{"raw_text": "杭州东"}}}}

当前已有的意图：
{intent_json}

用户的最新回答：
\"\"\"{user_message}\"\"\"

今天日期：{today}

只返回 JSON，不要带 markdown 标记。允许的字段：
{{
  "origin": "string",
  "destination": "string",
  "date": "YYYY-MM-DD",
  "earliest_time": "HH:MM",
  "return_required": true | false,
  "play_duration_hours": int
}}

被更新的字段才出现，未更新的字段不要出现。"""


# ====== 追问模板（避免让 LLM 自由生成，保证结构化）======

ASK_HEADER = "我来帮你规划行程。目前已收集到："

ASK_NEXT_ACTION_CROSS_CITY = "查到合适的车次"
ASK_NEXT_ACTION_INTRA_CITY = "规划好市内路线"

SLOT_LABELS = {
    "origin": "你从哪里出发？（例如：杭州电子科技大学研究生公寓）",
    "destination": "你想去哪里？（例如：宁波东钱湖）",
    "date": "你打算哪天出发？（YYYY-MM-DD 或「明天」「这周六」）",
    "earliest_time": "你最早几点能出门？（HH:MM）",
    "return_required": "需要顺便规划回程吗？（是/否）",
    "play_duration_hours": "大概玩几小时？",
}


# ====== 行程渲染模板 ======

ITINERARY_CARD_CROSS_CITY = """行程已规划好，整体可行 ✓

【去程】
- {dep_time} 从 {origin} 出发
  {leg1_summary}
- {train_depart} {train_code} {s1} → {s2}，{train_arrive} 到
  历时 {train_duration}，票价 {train_price} 元
- {leg2_summary}
- 预计 {play_start} 抵达 {destination}

【游玩】
- {play_start} ~ {play_end} {destination}（{play_hours} 小时）

{return_section}

【时间校验】
- 最早可出门：{earliest}
- 到 {s1} 通勤：{leg1_dur} 分钟
- 预计到站时间：{arrive_at_station}
- 火车发车：{train_depart}
- 缓冲余量：{buffer}
"""

ITINERARY_CARD_INTRA_CITY = """行程已规划好 ✓

【去程】
- {dep_time} 从 {origin} 出发
  {out_summary}
- 预计 {play_start} 抵达 {destination}

【游玩】
- {play_start} ~ {play_end} {destination}（{play_hours} 小时）

{return_section}
"""

INFEASIBLE_TEMPLATE = """⚠️ 当前方案不可行：

{reason}

{alternative}
"""

INFEASIBLE_ALTERNATIVE = "已为你自动尝试下一班次列车，请看上面的新方案。"
INFEASIBLE_NO_ALTERNATIVE = "当日后续已无更晚的车次。建议：\n- 提前 30~60 分钟出门\n- 或换一天出发\n- 或考虑汽车/自驾"


# ====== 行程可视化 Prompt ======

VISUALIZE_PROMPT = """你是一个行程可视化助手。根据以下行程数据，生成一份结构清晰、易于阅读的行程卡片。

可以使用 Markdown 表格、时间线、emoji 图标等方式让信息更直观。

【行程信息】
- 出发地：{origin}
- 目的地：{destination}
- 日期：{date}
- 最早出发时间：{earliest_time}
- 是否需要回程：{return_required}
- 游玩时长：{play_hours} 小时

【行程段详情】
{segments_detail}

请根据行程段详情生成一份可视化行程卡片，直接输出内容，不要加 markdown 代码块标记。
行程段中的字段含义如下：
返回结果
名称	类型	说明
status	string	本次 API 访问状态， 如果成功返回1，如果失败返回0。
info	string	访问状态值的说明，如果成功返回"ok"，失败返回错误原因，具体见 错误码说明 。
infocode	string	返回状态说明,10000代表正确,详情参阅 info 状态表
count	string	路径规划方案总数
route	object	返回的规划方案列表
origin	string	起点经纬度
destination	string	终点经纬度
transits	object	公交方案列表
distance		string	本条路线的总距离，单位：米
nightflag		nightflag	0：非夜班车；1：夜班车
segments		object	路线分段
walking		string	此分段中需要步行导航的信息
steps		参考 v3老接口
bus		string	此分段中需要公交导航的信息
steps		参考 v3老接口
railway		string	此分段中需要火车的信息
steps		参考 v3老接口
taxi
price	string	打车预计花费金额
drivetime	string	打车预计花费时间
distance	string	打车距离
polyline	string	线路点集合，通过 show_fields 控制返回与否
startpoint	string	打车起点经纬度
startname	string	打车起点名称
endpoint	string	打车终点经纬度
endname	string	打车终点名称
注意 以下字段如果需要返回，需要通过"show_fields"进行参数类设置。
cost		object	设置后可返回方案所需时间及费用成本 注意： taxi_fee 只 在 route 中返回，transit_fee 只在 segments 下返回。分段 steps 下不返回 cost。
duration		string	线路耗时，方案总耗时，包含等车时间， 单位：秒
taxi_fee		string	预估出租车费用
transit_fee		string	各换乘方案总花费
navi		object	设置后可返回详细导航动作指令
action		string	导航主要动作指令
assistant_action		string	导航辅助动作指令
walk_type		string	算路结果中存在的道路类型：
    0，普通道路 1，人行横道 3，地下通道 4，过街天桥
    5，地铁通道 6，公园 7，广场 8，扶梯 9，直梯
    10，索道 11，空中通道 12，建筑物穿越通道
    13，行人通道 14，游船路线 15，观光车路线 16，滑道
    18，扩路 19，道路附属连接线 20，阶梯 21，斜坡
    22，桥 23，隧道 30，轮渡
polyline		string	设置后可返回分路段坐标点串，两点间用",

通常跨城行程如下：步行至地铁站 -> 乘坐地铁至火车站/高铁站 -> 通过火车/高铁抵达目的城市站点 -> 通过地铁至目的地最近的地铁站 -> 通过步行至目的地
你需要从行程段详情中把对应信息提取出来，然后拼接，行程段中会返回5条路径，只取第一条路径即可。行程里面的每一段你都要展示出来，不能跳过任何一段
"""

# ====== POI 分类大类（用于 LLM 推断目的地类型） ======
# 高德地图 V5 POI 分类 - 仅保留 6 位一级大类（以 00 结尾）
# 大类中文名来自表格"大类"列，一字不改
POI_BIG_CATEGORIES_TABLE = """高德 POI 分类编码（一级大类，6 位以 00 结尾）：

010000 汽车服务
020000 汽车销售
030000 汽车维修
040000 摩托车服务
050000 餐饮服务
060000 购物服务
070000 生活服务
080000 体育休闲服务
090000 医疗保健服务
100000 住宿服务
110000 风景名胜
120000 商务住宅
130000 政府机构及社会团体
140000 科教文化服务
150000 交通设施服务
160000 金融保险服务
170000 公司企业
180000 道路附属设施
190000 地名地址信息
200000 公共设施
220000 事件活动
970000 室内设施
980000 虚拟数据
990000 通行设施

【任务】请根据目的地名称，判断它最可能属于上表中的哪一个一级大类。

常见映射示例：
- "东钱湖""西湖""黄山""千岛湖" → 风景名胜
- "浙江大学""复旦大学" → 科教文化服务
- "湖滨银泰""万象城" → 购物服务
- "西湖景区""普陀山" → 风景名胜
- "杭州电子科技大学" → 科教文化服务
- "家""小区""公寓""大厦" → 商务住宅
- "某某酒店""某某宾馆" → 住宿服务
- "某某餐厅""海底捞" → 餐饮服务

请仅返回一个 JSON，不要带 markdown 标记：
{{"category": "大类中文名", "confidence": "high|medium|low"}}

category 必须是上表中的一级大类中文名（一字不差）。如果不确定，选最接近的。
"""

# POI 分类推断 prompt
POI_CLASSIFY_PROMPT = """请判断以下目的地名称最可能属于高德 POI 分类的哪一个大类。

{poi_categories_table}

目的地名称：{destination_name}

请仅返回一个 JSON，不要带 markdown 标记：
{{"category": "大类中文名", "confidence": "high|medium|low"}}

category 必须是上表中的一级大类中文名（一字不差）。如果不确定，选最接近的。
"""

# 需要优先使用 POI 搜索而非 geocode 的大类中文名集合
# 这些类型如果用 geocode 容易返回住宅/地址坐标而非景点坐标
POI_SEARCH_PRIORITY_CATEGORIES = {"风景名胜", "科教文化服务", "购物服务", "体育休闲服务", "住宿服务"}