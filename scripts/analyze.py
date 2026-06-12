#!/usr/bin/env python3
"""
self-distill 分析引擎

输入：collect_self.CollectionResult
输出：纯摘要 dict（不包含任何 raw message text）

包含 3 个分析模块：
  1. analyze_expression    表达 DNA（词频/句式/口头禅/情绪）
  2. analyze_behavior      行为模式（活跃时段/协作/长度）
  3. infer_personality     趣味推断（MBTI/SBTI/动物/标签）
"""

import re
import json
import statistics
from collections import Counter, defaultdict
from typing import List, Dict, Any, Tuple
from datetime import datetime

# 为避免引入 jieba 依赖（pip install 慢），用简单字符切分 + 滑动窗口
# 这对中文足够好，对英文也好

# ---------- 停用词 ----------
# 注意：每个 token 必须独立成词，split() 按空白会把连续字当成一个字符串
STOP_WORDS_ZH = set("""
的 了 是 在 和 与 及 或 而 但 就 也 还 都 已 已经
我 这 你 那 他 她 它 我们 你们 他们 它们 自己
一个 一些 这个 那个 这些 那些 什么 怎么 为什么 多少 哪里 哪个
是 的 有 没 不 很 太 非常 比较 更 最
会 能 可以 可能 应该 必须 需要
对 错 好的 不好 是不是
然后 所以 因此 如果 虽然 但 可是
啊 哦 嗯 呢 吧 嘛 哈 嘿 唉 哎
就是说 比如 比方说 等 比如说
哈哈 哈哈哈 嗯嗯 啊啊
好 行 嗯 好嘞
""".split())

STOP_WORDS_EN = set("""
the a an and or but if then so because of in on at to for with by from
is are was were be been being have has had do does did
i you he she it we they me him her us them my your his its our their
this that these those what which who whom
as not no yes very too more most less
""".split())


# ---------- 系统消息过滤（黑名单正则） ----------
# dws 返回的消息 content 字段里可能含钉钉系统提示 / 机器人自动回复 / API 错误消息
# 这些会污染口头禅/关键词/情绪统计
# 策略：整条消息匹配任一 pattern → 跳过整条
import re as _re

SYSTEM_PHRASE_PATTERNS = [
    # 钉钉消息格式标记
    _re.compile(r'\[图片[^\]]*\]'),                 # [图片] / [图片消息]
    _re.compile(r'\[文件\]|\[日程\]|\[投票\]|\[任务\]|\[会议\]'),
    _re.compile(r'\(media[Ii]d=[^)]+\)'),          # (mediaId=xxx)
    _re.compile(r'\(media_id=[^)]+\)'),
    # dws API 错误/提示文本
    _re.compile(r'如需.{0,6}(下载|使用|授权|调用|安装)'),
    _re.compile(r'请使用.{0,6}(dws|命令|CLI|pat)'),
    _re.compile(r'请使(用|安装)'),
    _re.compile(r'需先授权'),
    _re.compile(r'(无权限|权限不足|未授权|scope)'),
    _re.compile(r'PAT_'),
    _re.compile(r'(中风险|低风险|高风险)'),
    # 系统提示前缀
    _re.compile(r'^\s*(注意|提示|警告|错误)[:：]'),
    _re.compile(r'^\s*⚠️'),
    _re.compile(r'^\s*❌'),
    _re.compile(r'^\s*❗'),
    # 钉钉机器人/AK 助手开头
    _re.compile(r'^\s*@?[Aa][Ii]\s*(助手|小助手|机器人)[:：]'),
    # 整条是短命令提示
    _re.compile(r'(download|upload).*?(如需|请使|必须)'),
    _re.compile(r'打开 (.*) 后 (即可|可) (使用|调用)'),
]


def is_system_message(content: str) -> bool:
    """判断一条消息是否是系统/机器人/错误消息

    返回 True = 是系统消息，应该跳过整条
    返回 False = 是正常用户消息，应该分析
    """
    if not content:
        return True
    content = content.strip()
    if not content:
        return True
    return any(p.search(content) for p in SYSTEM_PHRASE_PATTERNS)

# 业务工作词（用于判断"工作导向"）
WORK_KEYWORDS = set("""
周报 日报 周会 月报 项目 进度 对接 同步 评审 需求 方案 设计 开发
测试 上线 发布 代码 合并 分支 部署 测试环境 生产环境 bug 问题 排查 解决
文档 会议 纪要 反馈 对齐 讨论 确认 完成 截止 deadline 交付
命令 下载 使用 工具 脚本 skill 数据 接口 字段
表格 记录 视图 仪表盘
""".split())

# 抽象/体系词（用于 MBTI 的 N）
ABSTRACT_KEYWORDS = set("""
体系系统架构模式框架本质核心底层顶层方法论思维范式原则逻辑
抽象宏观全局端到端整体战略方向趋势意义价值
""".split())

# 情感词
POSITIVE_WORDS = set("""
好赞棒同意支持谢谢感谢感谢可以行不错赞好的不错没问题OK可以哈哈哈笑死绝了厉害牛
nice great awesome amazing love 哈哈 哈哈哈 哈 完美 牛啊 666 牛逼
好嘞 好的 好的好的 收到 收到收到 没问题 没问题鸭 ok OK
greate good thanks thank 不错哒 好耶 棒棒哒 太棒了
辛苦你了 多谢 哈哈 哈 嘻嘻 嗯嗯 666 强
""".split())

NEGATIVE_WORDS = set("""
不行不可以不行卡挂炸有问题有bug报错失败崩溃糟糕急紧急紧急help糟糕麻烦出问题
报错 失败 异常 崩溃 挂掉 卡住 卡死了 慢 慢了
bug BUG Bug 出错 错了 失败 失败了 不好使 不行啊
不行 不行不行 不行呀 不好 不好不好 很差 差劲
没用 无效 不行呗 麻烦 麻烦了 糟糕 糟了 急死了
hard difficult problem fail error exception timeout
吐了 烂 烂烂 烦 烦死了 烦人 麻了
""".split())

# 计划/截止/完成词（MBTI 的 J）
PLAN_WORDS = set("""
计划安排截止完成搞定按期按时截止时间ddl时间点里程碑节点
todo待办清单计划表日历提醒确认
""".split())

# 探索/假设/尝试词（MBTI 的 P）
EXPLORE_WORDS = set("""
试试想想尝试看看看看如果也许可能大概感觉似乎发现
探索假设猜测推断有没有可能会不会是
""".split())

# MBTI 维度特征
EI_FEATURES = {  # E: 外向 → 群聊多 / 动作词多
    "E_indicators": ["@", "拉群", "拉一下", "拉个群", "一起", "我们", "大家"],
    "I_indicators": ["私聊", "单独", "我自己", "我自己来", "直接说", "DM", "1v1"],
}

SN_FEATURES = {  # S: 实感 → 具体词 / N: 直觉 → 抽象词
    "S_indicators": ["数据", "数字", "截图", "表格", "list", "具体", "例子", "案例"],
    "N_indicators": ["体系", "架构", "本质", "核心", "模式", "范式", "方向", "意义"],
}

TF_FEATURES = {  # T: 思考 → 客观 / F: 情感 → 主观
    "T_indicators": ["效率", "对错", "逻辑", "原因", "因为", "所以", "分析"],
    "F_indicators": ["感受", "氛围", "感谢", "辛苦", "抱歉", "理解", "同感"],
}

JP_FEATURES = {  # J: 判断 → 计划 / P: 感知 → 探索
    "J_indicators": ["计划", "截止", "完成", "搞定", "ddl", "时间点", "确认"],
    "P_indicators": ["试试", "想想", "看", "可能", "如果", "探索", "感觉"],
}


# ---------- 工具函数 ----------

def tokenize_simple(text: str) -> List[str]:
    """简易分词：按字符切 1-2 字 + 提取连续中英文 + 标点分离"""
    # 移除 URL
    text = re.sub(r'https?://\S+', '', text)
    # 移除 markdown 链接 [text](url)
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
    # 移除钉钉消息格式 [图片消息](mediaId=xxx)
    text = re.sub(r'\[图片消息\]\(mediaId=[^)]+\)', '', text)
    # 移除 [日程] [文件] 等标记
    text = re.sub(r'\[[^\]]+\]', '', text)
    # 提取中文字符 1-2 字
    tokens = []
    # 中文 1-2 字
    for m in re.finditer(r'[\u4e00-\u9fff]{1,2}', text):
        tokens.append(m.group())
    # 英文（排除纯数字）
    for m in re.finditer(r'[a-zA-Z]{2,}', text):
        tokens.append(m.group().lower())
    return tokens


def make_ngrams(tokens: List[str], n: int) -> List[str]:
    """生成 n-gram"""
    if len(tokens) < n:
        return []
    return [tuple(tokens[i:i+n]) for i in range(len(tokens) - n + 1)]


def is_work_keyword(token: str) -> bool:
    """判断是否业务工作词"""
    return token in WORK_KEYWORDS or any(kw in token for kw in WORK_KEYWORDS if len(kw) >= 2)


# ---------- 模块 1: 表达 DNA ----------

def analyze_expression(messages: List[Any]) -> Dict[str, Any]:
    """
    表达 DNA 分析

    输入：List[ChatMessage]
    输出：snapshot 用的 expression_dna 字段
    """
    if not messages:
        return {
            "top_keywords": [],
            "top_bigrams": [],
            "top_trigrams": [],
            "catchphrases": [],
            "punctuation_density": {"question": 0.0, "exclamation": 0.0, "ellipsis": 0.0},
            "length_stats": {"mean": 0, "median": 0, "p90": 0, "p99": 0},
            "emotion": {"positive": 0.0, "negative": 0.0, "neutral": 1.0},
            "category": {"work_ratio": 0.0, "single_char_ratio": 0.0, "long_msg_ratio": 0.0},
        }

    all_tokens: List[str] = []
    bigrams: List[Tuple] = []
    trigrams: List[Tuple] = []

    total_chars = 0
    char_count_for_punct = 0
    question_count = 0
    exclamation_count = 0
    ellipsis_count = 0
    positive_count = 0
    negative_count = 0
    work_count = 0
    single_char_count = 0
    long_msg_count = 0
    msg_lengths: List[int] = []

    for msg in messages:
        content = msg.content
        if not content:
            continue
        msg_len = len(content)
        msg_lengths.append(msg_len)
        total_chars += msg_len

        # 标点
        for ch in content:
            char_count_for_punct += 1
            if ch == "?" or ch == "？":
                question_count += 1
            elif ch == "!" or ch == "！":
                exclamation_count += 1
            elif ch == "…" or ch == "...":
                ellipsis_count += 1

        # 长度特征
        if msg_len == 1 or (msg_len <= 2 and re.match(r'^[\u4e00-\u9fff]+$', content)):
            single_char_count += 1
        if msg_len > 50:
            long_msg_count += 1

        # 情感
        for w in POSITIVE_WORDS:
            if w in content:
                positive_count += 1
                break
        for w in NEGATIVE_WORDS:
            if w in content:
                negative_count += 1
                break

        # 分词 + n-gram
        tokens = tokenize_simple(content)
        all_tokens.extend(tokens)
        for t in tokens:
            if is_work_keyword(t):
                work_count += 1
                break

        bigrams.extend(make_ngrams(tokens, 2))
        trigrams.extend(make_ngrams(tokens, 3))

    n = len(messages)

    # 1-gram 频次（过滤停用词）
    counter_1 = Counter(all_tokens)
    counter_1 = Counter({
        t: c for t, c in counter_1.items()
        if t not in STOP_WORDS_ZH and t not in STOP_WORDS_EN and len(t) >= 1
    })
    top_keywords = counter_1.most_common(50)

    # 2-gram 频次
    counter_2 = Counter(bigrams)
    top_bigrams = [(f"{a} {b}", c) for (a, b), c in counter_2.most_common(20)]

    # 3-gram 频次
    counter_3 = Counter(trigrams)
    top_trigrams = [(f"{a} {b} {c}", c) for (a, b, c), c in counter_3.most_common(20)]

    # 口头禅：2-gram 频次 >=3 且出现率高
    catchphrases = [
        f"{a} {b}" for (a, b), c in counter_2.most_common(50)
        if c >= 3 and c / n >= 0.005  # 至少 0.5% 的消息包含
    ][:10]

    # 标点密度
    if char_count_for_punct > 0:
        punct = {
            "question": question_count / char_count_for_punct,
            "exclamation": exclamation_count / char_count_for_punct,
            "ellipsis": ellipsis_count / char_count_for_punct,
        }
    else:
        punct = {"question": 0.0, "exclamation": 0.0, "ellipsis": 0.0}

    # 长度分布
    if msg_lengths:
        mean = statistics.mean(msg_lengths)
        median = statistics.median(msg_lengths)
        msg_lengths_sorted = sorted(msg_lengths)
        p90_idx = int(len(msg_lengths_sorted) * 0.9)
        p99_idx = int(len(msg_lengths_sorted) * 0.99)
        p90 = msg_lengths_sorted[min(p90_idx, len(msg_lengths_sorted) - 1)]
        p99 = msg_lengths_sorted[min(p99_idx, len(msg_lengths_sorted) - 1)]
    else:
        mean = median = p90 = p99 = 0

    # 情绪
    total_emotion = positive_count + negative_count
    if total_emotion > 0:
        emo = {
            "positive": positive_count / n,
            "negative": negative_count / n,
            "neutral": 1 - total_emotion / n,
        }
    else:
        emo = {"positive": 0.0, "negative": 0.0, "neutral": 1.0}

    # 类别
    work_ratio = work_count / n if n > 0 else 0
    single_char_ratio = single_char_count / n if n > 0 else 0
    long_msg_ratio = long_msg_count / n if n > 0 else 0

    return {
        "top_keywords": [[kw, c] for kw, c in top_keywords],
        "top_bigrams": top_bigrams,
        "top_trigrams": top_trigrams,
        "catchphrases": catchphrases,
        "punctuation_density": punct,
        "length_stats": {
            "mean": round(mean, 1),
            "median": round(median, 1),
            "p90": p90,
            "p99": p99,
        },
        "emotion": {k: round(v, 3) for k, v in emo.items()},
        "category": {
            "work_ratio": round(work_ratio, 3),
            "single_char_ratio": round(single_char_ratio, 3),
            "long_msg_ratio": round(long_msg_ratio, 3),
        },
    }


# ---------- 模块 2: 行为模式 ----------

def analyze_behavior(messages: List[Any]) -> Dict[str, Any]:
    """
    行为模式分析

    输入：List[ChatMessage]
    输出：snapshot 用的 behavior_patterns 字段
    """
    if not messages:
        return {
            "active_hour_heatmap": [[0] * 24 for _ in range(7)],
            "top_collaborators": [],
            "group_vs_p2p": {"group": 0.0, "p2p": 0.0},
            "message_length_dist": {"mean": 0, "median": 0, "p90": 0, "p99": 0},
            "active_hour_top3": [],
            "weekend_ratio": 0.0,
            "late_night_ratio": 0.0,  # 0-5 点
        }

    # 7×24 热力图（按星期 0-6，小时 0-23）
    heatmap = [[0] * 24 for _ in range(7)]
    conv_counter: Counter = Counter()  # 按 conversation_title 统计
    group_msgs = 0
    p2p_msgs = 0
    weekend_msgs = 0
    late_night_msgs = 0
    msg_lengths: List[int] = []

    for msg in messages:
        # 解析 create_time
        try:
            # 格式 "2026-06-11 11:32:01"
            dt = datetime.strptime(msg.create_time, "%Y-%m-%d %H:%M:%S")
            weekday = dt.weekday()  # 0=Monday, 6=Sunday
            hour = dt.hour
            heatmap[weekday][hour] += 1
            if weekday >= 5:
                weekend_msgs += 1
            if 0 <= hour < 5:
                late_night_msgs += 1
        except (ValueError, TypeError):
            pass

        # 协作
        conv_counter[msg.conversation_title] += 1

        # 群聊/单聊
        if msg.is_single_chat:
            p2p_msgs += 1
        else:
            group_msgs += 1

        # 长度
        msg_lengths.append(len(msg.content))

    # 协作 Top 10（排除掉系统机器人/听记助手/AI 助手等）
    SYSTEM_NAMES = {"AI听记助手", "小智助手", "小助手明知", "钉钉小秘书",
                    "机器人", "通知", "系统消息", "系统", "Robot", "AI助手"}
    filtered_counter = Counter({
        name: c for name, c in conv_counter.items()
        if name not in SYSTEM_NAMES and not name.startswith("AI")
    })
    top_collaborators = filtered_counter.most_common(10)

    n = len(messages)
    group_ratio = group_msgs / n if n > 0 else 0
    p2p_ratio = p2p_msgs / n if n > 0 else 0
    weekend_ratio = weekend_msgs / n if n > 0 else 0
    late_night_ratio = late_night_msgs / n if n > 0 else 0

    # 长度分布
    if msg_lengths:
        mean = statistics.mean(msg_lengths)
        median = statistics.median(msg_lengths)
        msg_lengths_sorted = sorted(msg_lengths)
        p90_idx = int(len(msg_lengths_sorted) * 0.9)
        p99_idx = int(len(msg_lengths_sorted) * 0.99)
        p90 = msg_lengths_sorted[min(p90_idx, len(msg_lengths_sorted) - 1)]
        p99 = msg_lengths_sorted[min(p99_idx, len(msg_lengths_sorted) - 1)]
    else:
        mean = median = p90 = p99 = 0

    # Top 3 高峰小时
    hour_totals = [(h, sum(heatmap[d][h] for d in range(7))) for h in range(24)]
    hour_totals_sorted = sorted(hour_totals, key=lambda x: -x[1])
    top3_hours = [h for h, _ in hour_totals_sorted[:3]]

    return {
        "active_hour_heatmap": heatmap,
        "top_collaborators": [[name, c] for name, c in top_collaborators],
        "group_vs_p2p": {
            "group": round(group_ratio, 3),
            "p2p": round(p2p_ratio, 3),
        },
        "message_length_dist": {
            "mean": round(mean, 1),
            "median": round(median, 1),
            "p90": p90,
            "p99": p99,
        },
        "active_hour_top3": top3_hours,
        "weekend_ratio": round(weekend_ratio, 3),
        "late_night_ratio": round(late_night_ratio, 3),
    }


# ---------- 模块 3: 趣味推断（MBTI/SBTI/动物/标签） ----------

def _count_indicators(messages: List[Any], indicators: List[str]) -> Tuple[int, int]:
    """统计 indicators 出现次数（消息级 + 字符级）"""
    msg_hits = 0
    char_hits = 0
    for msg in messages:
        content = msg.content
        for ind in indicators:
            if ind in content:
                msg_hits += 1
                char_hits += content.count(ind)
                break  # 每条消息只算一次
    return msg_hits, char_hits


def infer_mbti(messages: List[Any]) -> Dict[str, str]:
    """MBTI 4 维度推断

    返回：{
        "EI": "I(72)", "SN": "N(63)", "TF": "T(68)", "JP": "J(71)",
        "mbti_code": "INTJ" / "⚠️信号弱 (I... 倾向)" / "均衡型" 等
    }

    设计原则：永不直接给"未分类"——但当 4 维 max 平均 < 40 时，
    说明数据信号很弱，**不要硬判 4 字母**，改用"信号弱 + 倾向字母"格式。
    """
    if not messages:
        return {
            "EI": "I(50)", "SN": "S(50)", "TF": "T(50)", "JP": "J(50)",
            "mbti_code": "均衡型（数据为空）",
        }

    n = len(messages)
    behavior = analyze_behavior(messages)
    expression = analyze_expression(messages)
    p2p_ratio = behavior["group_vs_p2p"]["p2p"]

    # EI
    e_msgs, e_chars = _count_indicators(messages, EI_FEATURES["E_indicators"])
    i_msgs, i_chars = _count_indicators(messages, EI_FEATURES["I_indicators"])
    group_ratio = 1 - p2p_ratio
    e_score = (group_ratio * 0.5 + (e_msgs / n) * 0.5) * 100
    i_score = (p2p_ratio * 0.5 + (i_msgs / n) * 0.5) * 100
    ei_label = "E" if e_score > i_score else "I"
    ei_score = max(e_score, i_score)

    # SN
    s_msgs, s_chars = _count_indicators(messages, SN_FEATURES["S_indicators"])
    n_msgs, n_chars = _count_indicators(messages, SN_FEATURES["N_indicators"])
    long_msg_ratio = expression["category"]["long_msg_ratio"]
    n_score = ((n_msgs / n) * 0.6 + long_msg_ratio * 0.4) * 100
    s_score = (s_msgs / n) * 100
    sn_label = "N" if n_score > s_score else "S"
    sn_score = max(n_score, s_score)

    # TF
    t_msgs, _ = _count_indicators(messages, TF_FEATURES["T_indicators"])
    f_msgs, _ = _count_indicators(messages, TF_FEATURES["F_indicators"])
    t_score = (t_msgs / n) * 100
    f_score = (f_msgs / n) * 100
    tf_label = "T" if t_score > f_score else "F"
    tf_score = max(t_score, f_score)

    # JP
    j_msgs, _ = _count_indicators(messages, JP_FEATURES["J_indicators"])
    p_msgs, _ = _count_indicators(messages, JP_FEATURES["P_indicators"])
    weekend_ratio = behavior["weekend_ratio"]
    j_extra = (1 - weekend_ratio) * 0.3
    j_score = (j_msgs / n) * 0.7 * 100 + j_extra * 100
    p_score = (p_msgs / n) * 100
    jp_label = "J" if j_score > p_score else "P"
    jp_score = max(j_score, p_score)

    # 综合判定：考虑信号强度
    scores = {"EI": ei_score, "SN": sn_score, "TF": tf_score, "JP": jp_score}
    labels = {"EI": ei_label, "SN": sn_label, "TF": tf_label, "JP": jp_label}
    avg_score = sum(scores.values()) / 4

    if avg_score < 40:
        # 信号太弱：不给 4 字母硬判，改用"信号弱 + 4 维倾向"格式
        mbti_code = f"⚠️信号弱({avg_score:.0f}%) " + "".join(labels.values())
    elif avg_score < 60:
        # 信号中等：保留 4 字母但加提示
        mbti_code = "".join(labels.values()) + f" (信号中 {avg_score:.0f}%)"
    else:
        mbti_code = "".join(labels.values())

    return {
        "EI": f"{ei_label}({int(min(ei_score, 99))})",
        "SN": f"{sn_label}({int(min(sn_score, 99))})",
        "TF": f"{tf_label}({int(min(tf_score, 99))})",
        "JP": f"{jp_label}({int(min(jp_score, 99))})",
        "mbti_code": mbti_code,
        "signal_strength": round(avg_score, 1),
    }


SBTI_CANDIDATES = [
    # name, 触发维度（每个 0-1）
    {
        "name": "深潜者",
        "score_func": lambda e, b: min(1.0, (
            max(0, (e["length_stats"]["mean"] - 30) / 80) * 0.4   # 长消息
            + e["category"]["work_ratio"] * 1.0                     # 业务词
            + e["category"]["long_msg_ratio"] * 0.6                 # 长消息占比
        )),
    },
    {
        "name": "甩手掌柜",
        "score_func": lambda e, b: min(1.0, (
            b["group_vs_p2p"]["group"] * 0.5                         # 群聊主导
            + e["category"]["single_char_ratio"] * 1.2               # 单字回复
            + (1 - e["category"]["long_msg_ratio"]) * 0.3            # 短消息多
        )),
    },
    {
        "name": "火警",
        "score_func": lambda e, b: min(1.0, (
            e["emotion"]["negative"] * 8                             # 负面词
            + (b.get("active_hour_top3", [12])[0] >= 22 or b.get("active_hour_top3", [12])[0] <= 5) * 0.3  # 深夜活跃
            + b["late_night_ratio"] * 2                              # 凌晨
        )),
    },
    {
        "name": "架构师",
        "score_func": lambda e, b: min(1.0, (
            sum(c for w, c in e["top_keywords"] if w in ABSTRACT_KEYWORDS) / max(1, len(messages_global)) * 4
            + max(0, (e["length_stats"]["mean"] - 25) / 60) * 0.4
            + (1 - e["punctuation_density"]["question"]) * 0.2
        )),
    },
    {
        "name": "侦察兵",
        "score_func": lambda e, b: min(1.0, (
            e["punctuation_density"]["question"] * 8                 # 问句
            + (e["length_stats"]["mean"] < 30) * 0.3                 # 短消息
            + b["late_night_ratio"] * 1.5                            # 凌晨
            + e["category"]["single_char_ratio"] * 1.0               # 单字
        )),
    },
    {
        "name": "记者",
        "score_func": lambda e, b: min(1.0, (
            sum(c for w, c in e["top_keywords"] if w in {"数据", "截图", "记录", "统计", "看", "查", "调研", "数"}) / max(1, len(messages_global)) * 4
            + b["top_collaborators"][0][1] / max(1, len(messages_global)) * 2  # 单一协作占比
            + (1 - b["weekend_ratio"]) * 0.2                         # 工作日专注
        )),
    },
    {
        "name": "指挥官",
        "score_func": lambda e, b: min(1.0, (
            (1 - b["late_night_ratio"]) * 0.3                        # 不凌晨
            + (1 - b["weekend_ratio"]) * 0.3                         # 工作日专注
            + b["top_collaborators"][0][1] / max(1, len(messages_global)) * 2 if b["top_collaborators"] else 0  # 单一指挥
            + len(b["top_collaborators"]) / 50 if b["top_collaborators"] else 0  # 协作广度反向
        )),
    },
    {
        "name": "讲师",
        "score_func": lambda e, b: min(1.0, (
            e["length_stats"]["mean"] / 50 * 0.4                     # 长消息
            + e["category"]["long_msg_ratio"] * 0.6                  # 长消息占比
            + (1 - e["category"]["single_char_ratio"]) * 0.2
        )),
    },
]

# 给每个 SBTI 类型加一句人话风格解读
SBTI_STYLE_MAP = {
    "深潜者": {"label": "深度内卷型", "desc": "一旦启动，停不下来，改到天亮也要让你'哇塞'！"},
    "甩手掌柜": {"label": "佛系指挥型", "desc": "动嘴不动手，群里从不亲自下场，永远是最后拍板的人"},
    "火警": {"label": "红色警戒型", "desc": "日常灭火专家，重大事故才出山，平时躺平等召唤"},
    "架构师": {"label": "PPT 永动机型", "desc": "三句话讲完本质，五张图说服全场，写文档比写代码还快"},
    "侦察兵": {"label": "信息掮客型", "desc": "群里潜伏最深的眼线，所有八卦都先从他嘴里流出"},
    "记者": {"label": "数据狂魔型", "desc": "没有数字不开口，没有图表不汇报，Excel 是第二母语"},
    "指挥官": {"label": "人形 Gantt 型", "desc": "DDL 写脸上，谁拖进度他第一个知道"},
    "讲师": {"label": "传道授业型", "desc": "三句讲不清就五句，五句讲不清就十句，恨不得把对方教会"},
}

# 全局 messages 引用（让 SBTI_CANDIDATES 的 score_func 能拿到消息总数）
messages_global: List[Any] = []


def infer_sbti(
    messages: List[Any],
    expression: Dict[str, Any],
    behavior: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """职场 SBTI 8 候选连续评分（永远返回 Top 3，绝不"未分类"）

    返回：[{type, score(0-100), evidence}, ...] top 3
    """
    global messages_global
    messages_global = messages

    if not messages:
        return [{"type": c["name"], "score": 50, "evidence": "数据样本为零，按 50 分兜底"} for c in SBTI_CANDIDATES[:3]]

    n = len(messages)
    candidates = []
    for c in SBTI_CANDIDATES:
        raw = c["score_func"](expression, behavior)
        score = int(min(100, max(0, raw * 100)))
        if score >= 30:  # 低于 30 分的候选不展示
            candidates.append({
                "type": c["name"],
                "score": score,
                "evidence": _sbti_evidence(c["name"], expression, behavior),
            })

    # 按分数降序，取 top 3
    candidates.sort(key=lambda x: -x["score"])

    # 如果全部 < 30 分，强制返回分数最高的 3 个
    if not candidates:
        for c in SBTI_CANDIDATES:
            raw = c["score_func"](expression, behavior)
            candidates.append({
                "type": c["name"],
                "score": max(1, int(raw * 100)),
                "evidence": "分数较低，证据不足",
            })
        candidates.sort(key=lambda x: -x["score"])
        return candidates[:3]

    return candidates[:3]


def _sbti_evidence(name: str, e: Dict[str, Any], b: Dict[str, Any]) -> str:
    """为每个 SBTI 类型生成针对性的证据说明"""
    avg = e["length_stats"]["mean"]
    work = e["category"]["work_ratio"]
    grp = b["group_vs_p2p"]["group"]
    sc = e["category"]["single_char_ratio"]
    neg = e["emotion"]["negative"]
    q = e["punctuation_density"]["question"]
    ln = b["late_night_ratio"]
    wd = b["weekend_ratio"]
    return {
        "深潜者": f"均长 {avg:.0f} 字、工作词 {work*100:.0f}%、长消息 {e['category']['long_msg_ratio']*100:.0f}%",
        "甩手掌柜": f"群聊 {grp*100:.0f}%、单字 {sc*100:.0f}%",
        "火警": f"负面词 {neg*100:.1f}%、凌晨 {ln*100:.1f}%",
        "架构师": f"抽象词 {sum(c for w,c in e['top_keywords'] if w in ABSTRACT_KEYWORDS)/max(1,len(messages_global))*100:.1f}%、均长 {avg:.0f}",
        "侦察兵": f"问句 {q*100:.1f}%、均长 {avg:.0f}、凌晨 {ln*100:.1f}%",
        "记者": f"收集类词密度 {sum(c for w,c in e['top_keywords'] if w in {'数据','截图','记录','统计','看','查'})/max(1,len(messages_global))*100:.1f}%、Top1 协作 {b['top_collaborators'][0][1] if b['top_collaborators'] else 0} 条",
        "指挥官": f"工作日专注 {1-wd:.0%}、单核协作 {b['top_collaborators'][0][1] if b['top_collaborators'] else 0} 条",
        "讲师": f"均长 {avg:.0f} 字、长消息 {e['category']['long_msg_ratio']*100:.0f}%",
    }.get(name, "数据样本中")


ANIMAL_CANDIDATES = [
    {
        "name": "猫头鹰",
        "score_func": lambda e, b: min(1.0,
            b["late_night_ratio"] * 4                                   # 夜间活跃
            + (b.get("active_hour_top3", [12])[0] in (22, 23, 0, 1, 2, 3)) * 0.4
            + e["punctuation_density"]["question"] * 1.5                # 问句
        ),
    },
    {
        "name": "蜜蜂",
        "score_func": lambda e, b: min(1.0,
            (e["length_stats"]["mean"] < 25) * 0.5                      # 短消息
            + (len(b["top_collaborators"]) / 15 if b["top_collaborators"] else 0)  # 协作广
            + e["category"]["single_char_ratio"] * 1.5                  # 单字多
        ),
    },
    {
        "name": "树懒",
        "score_func": lambda e, b: min(1.0,
            (1 - b["weekend_ratio"]) * 0.4                              # 工作日专注
            + (1 - b["late_night_ratio"]) * 0.3                        # 不夜猫
            + (e["length_stats"]["mean"] < 30) * 0.2                   # 短
        ),
    },
    {
        "name": "章鱼",
        "score_func": lambda e, b: min(1.0,
            b["group_vs_p2p"]["group"] * 0.7                            # 群聊
            + (1 - b["group_vs_p2p"]["p2p"]) * 0.2                      # 私聊少
            + len(b["top_collaborators"]) / 20 if b["top_collaborators"] else 0
        ),
    },
    {
        "name": "狼",
        "score_func": lambda e, b: min(1.0,
            b["group_vs_p2p"]["p2p"] * 0.5                             # 私聊
            + (b["top_collaborators"][0][1] / max(1, len(messages_global)) * 3 if b["top_collaborators"] else 0)  # Top1 占比
            + (1 - b["weekend_ratio"]) * 0.3
        ),
    },
    {
        "name": "孔雀",
        "score_func": lambda e, b: min(1.0,
            e["punctuation_density"]["exclamation"] * 15               # 感叹号
            + e["emotion"]["positive"] * 4                              # 积极词
        ),
    },
    {
        "name": "乌龟",
        "score_func": lambda e, b: min(1.0,
            e["category"]["long_msg_ratio"] * 1.5                      # 长消息
            + e["category"]["work_ratio"] * 1.0                         # 工作词
            + (1 - e["punctuation_density"]["exclamation"]) * 0.2      # 冷静
        ),
    },
    {
        "name": "狐狸",
        "score_func": lambda e, b: min(1.0,
            e["punctuation_density"]["question"] * 6                    # 问句
            + (e["length_stats"]["mean"] < 30) * 0.4
            + e["category"]["single_char_ratio"] * 1.0
        ),
    },
    {
        "name": "海狸",
        "score_func": lambda e, b: min(1.0,
            e["category"]["work_ratio"] * 1.2                           # 工作词
            + e["category"]["long_msg_ratio"] * 0.5
            + (1 - b["late_night_ratio"]) * 0.2                         # 稳定节奏
        ),
    },
    {
        "name": "海豚",
        "score_func": lambda e, b: min(1.0,
            b["group_vs_p2p"]["p2p"] * 0.4                              # 私聊
            + (b.get("active_hour_top3", [12])[0] in (8, 9, 10)) * 0.3  # 早活跃
            + e["emotion"]["positive"] * 2
        ),
    },
    {
        "name": "狮子",
        "score_func": lambda e, b: min(1.0,
            b["top_collaborators"][0][1] / max(1, len(messages_global)) * 5 if b["top_collaborators"] else 0
            + (1 - b["weekend_ratio"]) * 0.3
            + (1 - b["late_night_ratio"]) * 0.2
        ),
    },
    {
        "name": "变色龙",
        "score_func": lambda e, b: min(1.0,
            0.5                                                        # 兜底
            + len(set(b.get("active_hour_top3", []))) * 0.1
        ),
    },
]


def infer_animal(
    messages: List[Any],
    expression: Dict[str, Any],
    behavior: Dict[str, Any]
) -> Dict[str, Any]:
    """最像的动物推断（12 候选连续评分，返回 Top 3 排序）

    返回：{
        primary, primary_match, primary_evidence,
        secondary, secondary_match,
        tertiary, tertiary_match,
        all: [{name, score, evidence}, ...]
    }
    """
    global messages_global
    messages_global = messages

    if not messages:
        return {
            "primary": "变色龙", "primary_match": 50, "primary_evidence": "数据不足",
            "secondary": None, "secondary_match": 0,
            "tertiary": None, "tertiary_match": 0,
            "all": [{"name": c["name"], "score": 50, "evidence": "无数据"} for c in ANIMAL_CANDIDATES[:3]],
        }

    n = len(messages)
    candidates = []
    for c in ANIMAL_CANDIDATES:
        raw = c["score_func"](expression, behavior)
        score = int(min(100, max(0, raw * 100)))
        candidates.append({
            "name": c["name"],
            "score": score,
            "evidence": _animal_evidence(c["name"], expression, behavior),
        })

    # 按分数降序
    candidates.sort(key=lambda x: -x["score"])
    top3 = candidates[:3]
    primary = top3[0]
    secondary = top3[1] if len(top3) > 1 else None
    tertiary = top3[2] if len(top3) > 2 else None

    return {
        "primary": primary["name"],
        "primary_match": primary["score"],
        "primary_evidence": primary["evidence"],
        "secondary": secondary["name"] if secondary else None,
        "secondary_match": secondary["score"] if secondary else 0,
        "tertiary": tertiary["name"] if tertiary else None,
        "tertiary_match": tertiary["score"] if tertiary else 0,
        "all": candidates,  # 全部 12 候选 + 分数（深度报告用）
    }


def _animal_evidence(name: str, e: Dict[str, Any], b: Dict[str, Any]) -> str:
    avg = e["length_stats"]["mean"]
    work = e["category"]["work_ratio"]
    grp = b["group_vs_p2p"]["group"]
    p2p = b["group_vs_p2p"]["p2p"]
    late = b["late_night_ratio"]
    weekend = b["weekend_ratio"]
    long_msg = e["category"]["long_msg_ratio"]
    sc = e["category"]["single_char_ratio"]
    exc = e["punctuation_density"]["exclamation"]
    pos = e["emotion"]["positive"]
    q = e["punctuation_density"]["question"]
    top1 = b["top_collaborators"][0][1] if b["top_collaborators"] else 0
    n = max(1, len(messages_global))

    return {
        "猫头鹰": f"夜间 {late*100:.1f}%、问句 {q*100:.1f}%",
        "蜜蜂": f"均长 {avg:.0f}、协作 {len(b['top_collaborators'])} 人、单字 {sc*100:.0f}%",
        "树懒": f"工作日 {1-weekend:.0%}、不夜猫、均长 {avg:.0f}",
        "章鱼": f"群聊 {grp*100:.0f}%、协作广 {len(b['top_collaborators'])} 人",
        "狼": f"私聊 {p2p*100:.0f}%、Top1 占比 {top1/n*100:.0f}%",
        "孔雀": f"感叹号 {exc*100:.2f}%、积极词 {pos*100:.1f}%",
        "乌龟": f"长消息 {long_msg*100:.0f}%、工作词 {work*100:.0f}%",
        "狐狸": f"问句 {q*100:.1f}%、均长 {avg:.0f}、单字 {sc*100:.0f}%",
        "海狸": f"工作词 {work*100:.0f}%、长消息 {long_msg*100:.0f}%",
        "海豚": f"私聊 {p2p*100:.0f}%、早活跃、{pos*100:.0f}% 积极",
        "狮子": f"Top1 占比 {top1/n*100:.0f}%、工作日 {1-weekend:.0%}",
        "变色龙": f"全场景适应（{len(set(b.get('active_hour_top3',[])))} 高峰时段）",
    }.get(name, "综合特征")


def infer_tags(
    expression: Dict[str, Any],
    behavior: Dict[str, Any],
    mbti: Dict[str, str]
) -> List[str]:
    """性格标签 Top 5"""
    tags = []

    avg_len = expression["length_stats"]["mean"]
    work_ratio = expression["category"]["work_ratio"]
    late_night = behavior["late_night_ratio"]
    weekend = behavior["weekend_ratio"]
    question_density = expression["punctuation_density"]["question"]
    p2p_ratio = behavior["group_vs_p2p"]["p2p"]
    work_keywords_set = set(t for t, _ in expression["top_keywords"][:30])

    # 节奏型
    if late_night > 0.1:
        tags.append("夜猫子")
    elif 0.05 < late_night <= 0.1:
        tags.append("轻度夜猫")
    else:
        tags.append("早起型")

    if weekend < 0.05:
        tags.append("工作日专注")
    elif weekend > 0.2:
        tags.append("全时型")

    # 表达型
    if avg_len > 60:
        tags.append("阐释型")
    elif avg_len < 15:
        tags.append("极简派")
    else:
        tags.append("均衡型")

    if question_density > 0.05:
        tags.append("好奇型")
    if work_ratio > 0.3:
        tags.append("细节敏感")
    if work_ratio < 0.1 and p2p_ratio > 0.5:
        tags.append("关系导向")

    # 抽象/具体
    abstract_kw_in_top = work_keywords_set & ABSTRACT_KEYWORDS
    if len(abstract_kw_in_top) >= 2:
        tags.append("抽象派")

    # MBTI 衍生
    mbti_code = mbti.get("EI", "")[0] + mbti.get("SN", "")[0] + mbti.get("TF", "")[0] + mbti.get("JP", "")[0]
    if mbti_code == "INTJ":
        tags.append("策略家")
    elif mbti_code == "ENTJ":
        tags.append("指挥官")
    elif mbti_code == "INFP":
        tags.append("理想家")

    # 去重，限 5
    seen = set()
    unique = []
    for t in tags:
        if t not in seen:
            seen.add(t)
            unique.append(t)
    return unique[:5]


# ---------- 模块 4: 趣味人设（原型图核心） ----------

# 决策风格（从多个信号综合）
DECISION_STYLES = [
    {
        "name": "数据驱动型",
        "desc": "做决定前先看数字，凭感觉不如凭报表",
        # 不 min(1.0)：让原始分数超过 1.0，避免多个候选都=1.0 后归一化都=100%
        "score_func": lambda e, b: (
            e["category"]["work_ratio"] * 2
            + e["length_stats"]["mean"] / 50 * 0.5
            + (1 - e["punctuation_density"]["question"]) * 0.3
        ),
    },
    {
        "name": "直觉闪电型",
        "desc": "想 5 分钟就拍板，事后复盘时常说'我当时就感觉'",
        "score_func": lambda e, b: (
            e["category"]["single_char_ratio"] * 2
            + (e["length_stats"]["mean"] < 30) * 0.5
            + e["punctuation_density"]["exclamation"] * 5
        ),
    },
    {
        "name": "深思熟虑型",
        "desc": "想完再想，确认完再确认，但出手一定稳",
        "score_func": lambda e, b: (
            e["category"]["long_msg_ratio"] * 1.5
            + (1 - e["category"]["single_char_ratio"]) * 0.5
            + (1 - e["punctuation_density"]["exclamation"]) * 0.3
        ),
    },
    {
        "name": "协作共识型",
        "desc": "一个人定不下来，要拉几个人过一遍才放心",
        "score_func": lambda e, b: (
            len(b["top_collaborators"]) / 10 if b["top_collaborators"] else 0
            + b["group_vs_p2p"]["group"] * 0.5
        ),
    },
]

# 沟通偏好
COMMUNICATION_STYLES = [
    {
        "name": "直球型",
        "desc": "有话直说，不绕弯子，省得大家猜",
        "score_func": lambda e, b: (
            (1 - e["punctuation_density"]["question"]) * 0.5
            + e["category"]["work_ratio"] * 0.5
            + e["length_stats"]["mean"] / 50 * 0.3
        ),
    },
    {
        "name": "委婉派",
        "desc": "说不出口的话，换三个说法再发",
        "score_func": lambda e, b: (
            e["punctuation_density"]["question"] * 2
            + e["category"]["long_msg_ratio"] * 0.8
            + e["emotion"]["positive"] * 2
        ),
    },
    {
        "name": "数据党",
        "desc": "没有数字不开口，开口就是百分比",
        "score_func": lambda e, b: (
            e["category"]["work_ratio"] * 2
            + e["category"]["long_msg_ratio"] * 0.5
        ),
    },
    {
        "name": "气氛组",
        "desc": "群里没他冷一半，主要功能是调和气氛",
        "score_func": lambda e, b: (
            b["group_vs_p2p"]["group"] * 0.7
            + e["emotion"]["positive"] * 3
            + e["punctuation_density"]["exclamation"] * 5
        ),
    },
]

# 压力反应
STRESS_RESPONSES = [
    {
        "name": "沉默消化型",
        "desc": "越有压力越安静，群里看不到他，但活已经干完",
        "score_func": lambda e, b: (
            (1 - e["punctuation_density"]["exclamation"]) * 0.3
            + b["late_night_ratio"] * 2  # 压力来时凌晨干活
            + e["category"]["work_ratio"] * 0.5
        ),
    },
    {
        "name": "快速响应型",
        "desc": "压力 = 立刻动起来，先干再说",
        "score_func": lambda e, b: (
            e["category"]["single_char_ratio"] * 1.5
            + (e["length_stats"]["mean"] < 25) * 0.5
        ),
    },
    {
        "name": "向外求援型",
        "desc": "压力来了第一反应是拉人开会/求助",
        "score_func": lambda e, b: (
            len(b["top_collaborators"]) / 10 if b["top_collaborators"] else 0
            + e["punctuation_density"]["question"] * 3
        ),
    },
]

# 价值观倾向（基于关键词 + 行为模式）
VALUE_TENDENCIES = [
    {
        "name": "效率优先",
        "desc": "凡事先问'这能快一点吗'",
        "score_func": lambda e, b: (
            sum(c for w, c in e["top_keywords"] if w in {"快", "效率", "提速", "赶", "急", "节奏", "时间", "ddl", "DDL"}) / max(1, len(messages_global)) * 5
            + (1 - e["length_stats"]["mean"] / 100) * 0.3
        ),
    },
    {
        "name": "质量优先",
        "desc": "宁可慢一点也要做对，宁可磨一磨也要做透",
        "score_func": lambda e, b: (
            e["category"]["long_msg_ratio"] * 1.5
            + e["category"]["work_ratio"] * 0.5
        ),
    },
    {
        "name": "关系优先",
        "desc": "先把人处好，事自然就顺了",
        "score_func": lambda e, b: (
            b["group_vs_p2p"]["p2p"] * 0.5
            + len(b["top_collaborators"]) / 15 if b["top_collaborators"] else 0
            + e["emotion"]["positive"] * 2
        ),
    },
    {
        "name": "创新优先",
        "desc": "看到新东西就兴奋，讨厌重复劳动",
        "score_func": lambda e, b: (
            e["punctuation_density"]["question"] * 3
            + sum(c for w, c in e["top_keywords"] if w in {"新", "试", "做", "想", "看", "玩", "搞"}) / max(1, len(messages_global)) * 3
        ),
    },
]

# 信息处理风格
INFO_PROCESSING_STYLES = [
    {
        "name": "视觉优先",
        "desc": "看到'截图''图'就秒懂，看文字容易走神",
        "score_func": lambda e, b: (
            sum(c for w, c in e["top_keywords"] if w in {"图", "截图", "看", "图里", "图上"}) / max(1, len(messages_global)) * 5
        ),
    },
    {
        "name": "文字深度",
        "desc": "读长文不费力，反而觉得短消息说不清",
        "score_func": lambda e, b: (
            e["category"]["long_msg_ratio"] * 2
            + e["length_stats"]["mean"] / 50 * 0.5
        ),
    },
    {
        "name": "口头快闪",
        "desc": "消息短平快，3 句话解决战斗",
        "score_func": lambda e, b: (
            e["category"]["single_char_ratio"] * 1.5
            + (e["length_stats"]["mean"] < 25) * 0.5
        ),
    },
    {
        "name": "结构化记录",
        "desc": "凡事 1/2/3 列出来，不喜欢想到哪说到哪",
        "score_func": lambda e, b: (
            e["category"]["work_ratio"] * 1.5
            + e["category"]["long_msg_ratio"] * 0.8
        ),
    },
]


def infer_decision_style(e: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Any]:
    """决策风格（4 选 1，返回 primary + secondary）"""
    global messages_global
    messages_global = messages_global or []

    scored = []
    for c in DECISION_STYLES:
        raw = c["score_func"](e, b)
        scored.append({"name": c["name"], "desc": c["desc"], "score": int(raw * 100)})
    # 归一化到 0-100
    max_score = max(s["score"] for s in scored) or 1
    for s in scored:
        s["score"] = int(s["score"] * 100 / max_score)
    scored.sort(key=lambda x: -x["score"])
    primary = scored[0]
    secondary = scored[1] if len(scored) > 1 else None
    return {
        "primary": primary["name"],
        "primary_desc": primary["desc"],
        "primary_score": primary["score"],
        "secondary": secondary["name"] if secondary else None,
        "secondary_desc": secondary["desc"] if secondary else None,
        "secondary_score": secondary["score"] if secondary else 0,
        "all": scored,
    }


def infer_communication_style(e: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Any]:
    """沟通偏好（4 选 1，返回 primary + secondary）"""
    scored = []
    for c in COMMUNICATION_STYLES:
        raw = c["score_func"](e, b)
        scored.append({"name": c["name"], "desc": c["desc"], "score": int(raw * 100)})
    max_score = max(s["score"] for s in scored) or 1
    for s in scored:
        s["score"] = int(s["score"] * 100 / max_score)
    scored.sort(key=lambda x: -x["score"])
    primary = scored[0]
    secondary = scored[1] if len(scored) > 1 else None
    return {
        "primary": primary["name"],
        "primary_desc": primary["desc"],
        "primary_score": primary["score"],
        "secondary": secondary["name"] if secondary else None,
        "secondary_desc": secondary["desc"] if secondary else None,
        "secondary_score": secondary["score"] if secondary else 0,
        "all": scored,
    }


def infer_stress_response(e: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Any]:
    """压力反应（3 选 1，返回 primary + secondary）"""
    scored = []
    for c in STRESS_RESPONSES:
        raw = c["score_func"](e, b)
        scored.append({"name": c["name"], "desc": c["desc"], "score": int(raw * 100)})
    max_score = max(s["score"] for s in scored) or 1
    for s in scored:
        s["score"] = int(s["score"] * 100 / max_score)
    scored.sort(key=lambda x: -x["score"])
    primary = scored[0]
    secondary = scored[1] if len(scored) > 1 else None
    return {
        "primary": primary["name"],
        "primary_desc": primary["desc"],
        "primary_score": primary["score"],
        "secondary": secondary["name"] if secondary else None,
        "secondary_desc": secondary["desc"] if secondary else None,
        "secondary_score": secondary["score"] if secondary else 0,
        "all": scored,
    }


def infer_value_tendency(e: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Any]:
    """价值观倾向（4 选 1，返回 primary + secondary）"""
    global messages_global
    messages_global = messages_global or []
    scored = []
    for c in VALUE_TENDENCIES:
        raw = c["score_func"](e, b)
        scored.append({"name": c["name"], "desc": c["desc"], "score": int(raw * 100)})
    max_score = max(s["score"] for s in scored) or 1
    for s in scored:
        s["score"] = int(s["score"] * 100 / max_score)
    scored.sort(key=lambda x: -x["score"])
    primary = scored[0]
    secondary = scored[1] if len(scored) > 1 else None
    return {
        "primary": primary["name"],
        "primary_desc": primary["desc"],
        "primary_score": primary["score"],
        "secondary": secondary["name"] if secondary else None,
        "secondary_desc": secondary["desc"] if secondary else None,
        "secondary_score": secondary["score"] if secondary else 0,
        "all": scored,
    }


def infer_info_processing(e: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Any]:
    """信息处理风格（4 选 1，返回 primary + secondary）"""
    global messages_global
    messages_global = messages_global or []
    scored = []
    for c in INFO_PROCESSING_STYLES:
        raw = c["score_func"](e, b)
        scored.append({"name": c["name"], "desc": c["desc"], "score": int(raw * 100)})
    max_score = max(s["score"] for s in scored) or 1
    for s in scored:
        s["score"] = int(s["score"] * 100 / max_score)
    scored.sort(key=lambda x: -x["score"])
    primary = scored[0]
    secondary = scored[1] if len(scored) > 1 else None
    return {
        "primary": primary["name"],
        "primary_desc": primary["desc"],
        "primary_score": primary["score"],
        "secondary": secondary["name"] if secondary else None,
        "secondary_desc": secondary["desc"] if secondary else None,
        "secondary_score": secondary["score"] if secondary else 0,
        "all": scored,
    }

# 职场 SBTI 风格映射（基于 SBTI 标签 + 性格 → 人类可读的中文风格）
SBTI_STYLE_MAP = {
    "深潜者": {
        "label": "深度内卷型",
        "desc_template": "一旦启动，停不下来，改到天亮也要让你'哇塞'！",
    },
    "甩手掌柜": {
        "label": "佛系指挥型",
        "desc_template": "动嘴不动手，群里从不亲自下场，永远是最后拍板的人",
    },
    "火警": {
        "label": "红色警戒型",
        "desc_template": "日常灭火专家，重大事故才出山，平时躺平等召唤",
    },
    "架构师": {
        "label": "PPT 永动机型",
        "desc_template": "三句话讲完本质，五张图说服全场，写文档比写代码还快",
    },
    "侦察兵": {
        "label": "信息掮客型",
        "desc_template": "群里潜伏最深的眼线，所有八卦都先从他嘴里流出",
    },
    "记者": {
        "label": "数据狂魔型",
        "desc_template": "没有数字不开口，没有图表不汇报，Excel 是第二母语",
    },
    "指挥官": {
        "label": "人形 Gantt 型",
        "desc_template": "DDL 写脸上，谁拖进度他第一个知道",
    },
    "讲师": {
        "label": "传道授业型",
        "desc_template": "三句讲不清就五句，五句讲不清就十句，恨不得把对方教会",
    },
}

# 摸鱼/勤奋伪装的趣味标签
SNEAKY_LABELS = [
    ("摸鱼伪装大师", "白天消息多到爆炸，KPI 进度全靠嘴遁"),
    ("零摸鱼型", "凌晨不发、周末不发，勤奋到让同事自愧不如"),
    ("隐形劳模型", "群里静悄悄，私下已交付，活儿都在看不见的地方"),
    ("摸鱼 KOL", "群内话题全靠他带，KPI 推进全靠他催"),
    ("假装摸鱼型", "你以为他在摸鱼，其实他在同步 5 个项目"),
    ("暗戳戳干活型", "不 @ 不冒泡，重要节点准时出现"),
]


def infer_sbti_style(sbti_list: List[Dict[str, Any]]) -> Dict[str, str]:
    """从 SBTI 列表推断风格标签 + 解读

    设计原则：永不返回「未分类选手」「????」这种空 fallback。
    任何数据量下都给一个有意义的人设标签 + 一句话总结。
    """
    # 兜底 1：完全没有数据 → 均衡型
    if not sbti_list:
        return {
            "label": "均衡型",
            "code": "均衡",
            "desc": "暂无足够数据画像，但既然你点开了，说明你对自己有好奇",
            "score": 0,
        }

    primary = sbti_list[0]
    type_name = primary["type"]
    style = SBTI_STYLE_MAP.get(type_name)

    # 兜底 2：SBTI_STYLE_MAP 漏映射（如临时新增的类型）→ 通用模板
    if not style:
        return {
            "label": f"{type_name}型",
            "code": type_name,
            "desc": primary.get("evidence", "综合表现突出"),
            "score": primary.get("score", 0),
        }

    return {
        "label": style["label"],
        "code": type_name,
        "desc": style["desc_template"],
        "score": primary.get("score", 0),
    }


def infer_sneaky_label(behavior: Dict[str, Any], expression: Dict[str, Any]) -> Dict[str, str]:
    """推断"摸鱼伪装"标签（幽默风格）"""
    late_night = behavior["late_night_ratio"]
    weekend = behavior["weekend_ratio"]
    group_ratio = behavior["group_vs_p2p"]["group"]
    avg_len = expression["length_stats"]["mean"]
    question_density = expression["punctuation_density"]["question"]
    late_night_inverse = 1 - late_night  # 越低越勤奋
    weekend_inverse = 1 - weekend

    # 选标签：按"勤奋程度"挑
    if late_night < 0.05 and weekend < 0.05:
        label_idx = 1  # 零摸鱼型
    elif group_ratio > 0.5 and question_density > 0.05:
        label_idx = 3  # 摸鱼 KOL
    elif group_ratio > 0.3 and avg_len < 25:
        label_idx = 4  # 假装摸鱼
    elif avg_len < 30 and question_density > 0.05:
        label_idx = 5  # 暗戳戳干活
    elif group_ratio < 0.3 and avg_len > 50:
        label_idx = 2  # 隐形劳模
    else:
        label_idx = 0  # 摸鱼伪装大师（默认）

    name, evidence = SNEAKY_LABELS[label_idx]
    return {"label": name, "evidence": evidence}


def infer_personality_traits(
    expression: Dict[str, Any],
    behavior: Dict[str, Any],
    personality: Dict[str, Any],
    mbti_code: str,
) -> List[Dict[str, str]]:
    """生成 6 个性格特征条目（icon + 标题 + 描述）"""
    avg_len = expression["length_stats"]["mean"]
    median_len = expression["length_stats"]["median"]
    p90_len = expression["length_stats"]["p90"]
    work_ratio = expression["category"]["work_ratio"]
    single_char_ratio = expression["category"]["single_char_ratio"]
    long_msg_ratio = expression["category"]["long_msg_ratio"]
    late_night = behavior["late_night_ratio"]
    weekend = behavior["weekend_ratio"]
    group_ratio = behavior["group_vs_p2p"]["group"]
    p2p_ratio = behavior["group_vs_p2p"]["p2p"]
    active_hours = behavior.get("active_hour_top3", [])
    mbti = personality["mbti"]
    ei = mbti.get("EI", "I(50)")[0]
    sn = mbti.get("SN", "S(50)")[0]
    tf = mbti.get("TF", "T(50)")[0]
    jp = mbti.get("JP", "J(50)")[0]

    traits = []

    # 1. 平均长度 → 表达欲 / 简洁
    if avg_len > 60:
        traits.append({"icon": "💡", "title": "会做脑暴", "desc": f"不会做报表（均长 {avg_len:.0f} 字）"})
    elif avg_len < 15:
        traits.append({"icon": "💡", "title": "极简派", "desc": f"少说多干（均长 {avg_len:.0f} 字）"})
    else:
        traits.append({"icon": "💡", "title": "会做脑暴", "desc": f"不会做报表（均长 {avg_len:.0f} 字）"})

    # 2. 协作集中度 → 关系深度
    collab = behavior["top_collaborators"]
    if collab:
        top1_name, top1_count = collab[0]
        if top1_count > 0.4 * sum(c for _, c in collab) and len(collab) >= 3:
            traits.append({"icon": "🤝", "title": "单核协作", "desc": f"和 {top1_name} 深度绑定"})
        else:
            traits.append({"icon": "🤝", "title": "广泛协作", "desc": f"{len(collab)} 个核心伙伴"})

    # 3. 单聊 vs 群聊
    if p2p_ratio > 0.7:
        traits.append({"icon": "☕", "title": "咖啡续命", "desc": f"私聊占 {p2p_ratio*100:.0f}%，一对一深聊王"})
    elif group_ratio > 0.7:
        traits.append({"icon": "☕", "title": "群内活跃", "desc": f"群聊占 {group_ratio*100:.0f}%，社交发动机"})
    else:
        traits.append({"icon": "☕", "title": "咖啡续命", "desc": f"私聊/群聊均衡（{p2p_ratio*100:.0f}% / {group_ratio*100:.0f}%）"})

    # 4. 工作词 / 长消息 → 深度
    if long_msg_ratio > 0.2:
        traits.append({"icon": "⏰", "title": f"擅长把 deadline 谈成 lifeline",
                       "desc": f"长消息 {long_msg_ratio*100:.0f}% 说明你能写会道"})
    elif work_ratio > 0.3:
        traits.append({"icon": "⏰", "title": "DDL 把控者",
                       "desc": f"工作词密度 {work_ratio*100:.0f}%，业务感强"})
    else:
        traits.append({"icon": "⏰", "title": "轻度内卷",
                       "desc": f"工作词 {work_ratio*100:.0f}%，还有闲聊空间"})

    # 5. 表达 DNA → 性格
    cat_work = work_ratio > 0.2
    if cat_work:
        traits.append({"icon": "📝", "title": "随身带便签",
                       "desc": "记性全靠它（工作词密度高）"})
    else:
        traits.append({"icon": "📝", "title": "随性表达",
                       "desc": f"工作词 {work_ratio*100:.0f}%，不拘一格"})

    # 6. 节奏
    if late_night < 0.05 and weekend < 0.1:
        traits.append({"icon": "😎", "title": "乐观积极",
                       "desc": "从不内耗，主打一个心大"})
    else:
        traits.append({"icon": "😎", "title": "夜猫子 / 周末活跃",
                       "desc": f"凌晨 {late_night*100:.0f}% / 周末 {weekend*100:.0f}%"})

    return traits[:6]


def infer_kpi_happy(
    behavior: Dict[str, Any],
    expression: Dict[str, Any],
    collection_summary: Dict[str, Any],
) -> List[Dict[str, str]]:
    """生成 3-4 个"快乐版 KPI"（基于真实数据 + 幽默包装）"""
    avg_len = expression["length_stats"]["mean"]
    late_night = behavior["late_night_ratio"]
    weekend = behavior["weekend_ratio"]
    work_ratio = expression["category"]["work_ratio"]
    question_density = expression["punctuation_density"]["question"]
    active_hours = behavior.get("active_hour_top3", [])
    message_count = collection_summary.get("chat", {}).get("message_count", 0)

    kpis = []

    # 1. 准时打卡（按时下班）
    if late_night < 0.05 and active_hours and max(active_hours) <= 19:
        kpis.append({"name": "按时下班", "evidence": "（必达）", "icon": "✓"})
    elif late_night < 0.1:
        kpis.append({"name": "按时下班", "evidence": "（基本必达）", "icon": "✓"})
    else:
        kpis.append({"name": "按时下班", "evidence": "（梦想还是要有的）", "icon": "✗"})

    # 2. 认真摸鱼
    if work_ratio < 0.2:
        kpis.append({"name": "认真摸鱼", "evidence": "（专业级）", "icon": "✓"})
    elif work_ratio < 0.4:
        kpis.append({"name": "认真摸鱼", "evidence": "（业余级）", "icon": "✓"})
    else:
        kpis.append({"name": "认真摸鱼", "evidence": "（心向往之）", "icon": "✗"})

    # 3. 准时打卡（消息频率）
    if message_count > 50:
        kpis.append({"name": "准时打卡", "evidence": f"（{message_count} 条已读）", "icon": "✓"})
    elif message_count > 20:
        kpis.append({"name": "准时打卡", "evidence": "（勉强）", "icon": "✓"})
    else:
        kpis.append({"name": "准时打卡", "evidence": "（今日休）", "icon": "✗"})

    return kpis


def generate_slogan_long(
    personality: Dict[str, Any],
    mbti_code: str,
    slogan_short: List[str],
) -> str:
    """生成 3 行版职场宣言"""
    # 模板：3 行（押韵 / 节奏感）
    templates = {
        "INTJ": "打工赚小钱，\n脑洞赚大钱，\n快乐最值钱！",
        "INTP": "质疑一切，\n不质疑快乐，\n不质疑自己。",
        "ENTJ": "目标清晰，\n执行到位，\n不浪费人生。",
        "ENTP": "想到就试，\n试错就改，\n改完再战。",
        "INFJ": "安静地想，\n安静地做，\n安静地发光。",
        "INFP": "保持真诚，\n保持好奇，\n保持温柔。",
        "ENFJ": "把人放第一位，\n把事做到极致，\n把日子过成诗。",
        "ENFP": "有一百个想法，\n走通一个，\n就够了不起。",
        "ISTJ": "把事做对，\n把人做好，\n把日子过稳。",
        "ISFJ": "先照顾好你，\n再照顾好世界。",
        "ESTJ": "执行大于讨论，\n结果大于过程，\n效率大于完美。",
        "ESFJ": "气氛是协作的燃料，\n人是气氛的主角。",
        "ISTP": "工具用得熟，\n问题就少，\n时间就多。",
        "ISFP": "慢工出细活，\n细活出好活。",
        "ESTP": "先动起来，\n再优化，\n再迭代。",
        "ESFP": "现场是唯一的真相。",
    }
    if mbti_code in templates:
        return templates[mbti_code]

    # Fallback
    if slogan_short:
        return slogan_short[0] + "，" + (slogan_short[1] if len(slogan_short) > 1 else "快乐最值钱")
    return "打工赚小钱，\n脑洞赚大钱，\n快乐最值钱！"


# ---------- 顶层入口 ----------

def analyze_all(messages: List[Any]) -> Dict[str, Any]:
    """完整分析入口（深度分析报告的基础）

    输入：List[ChatMessage]
    输出：{
        # 完整数据层（深度报告用）
        expression_dna, behavior_patterns, personality,
        # 趣味推断（深度报告用）
        sbti_top3, animal_top3, decision_style, communication_style,
        stress_response, value_tendency, info_processing,
        slogan_candidates, slogan_long, kpi_happy, personality_traits, sneaky_label,
        # 卡片二次抽象用（兼容旧版）
        sbti_style,
    }
    """
    # 入口过滤：剥离 dws 返回的系统消息/机器人回复/API 错误文本
    # 这些会污染口头禅/关键词/情绪统计
    raw_count = len(messages)
    messages = [m for m in messages if not is_system_message(m.content)]
    filtered_count = raw_count - len(messages)
    if filtered_count > 0:
        print(f"  过滤 {filtered_count} 条系统消息（{raw_count} → {len(messages)}）",
              file=__import__("sys").stderr)

    print(f"  分析 {len(messages)} 条消息...", file=__import__("sys").stderr)

    expression = analyze_expression(messages)
    behavior = analyze_behavior(messages)
    mbti = infer_mbti(messages)
    sbti = infer_sbti(messages, expression, behavior)
    animal = infer_animal(messages, expression, behavior)
    tags = infer_tags(expression, behavior, mbti)
    # 4 字母（仅标准 4 维；跳过 mbti_code/signal_strength）
    mbti_code = "".join(d[0] for d in mbti.values() if isinstance(d, str) and "(" in d)

    # 趣味推断（5 维度 × N 选 1）
    decision_style = infer_decision_style(expression, behavior)
    communication_style = infer_communication_style(expression, behavior)
    stress_response = infer_stress_response(expression, behavior)
    value_tendency = infer_value_tendency(expression, behavior)
    info_processing = infer_info_processing(expression, behavior)

    # 人设化（用于卡片）
    sbti_style = infer_sbti_style(sbti)
    sneaky_label = infer_sneaky_label(behavior, expression)
    personality_traits = infer_personality_traits(expression, behavior, {"mbti": mbti}, mbti_code)

    slogans = generate_slogans(tags, [w for w, _ in expression["top_keywords"][:20]], mbti)
    slogan_long = generate_slogan_long({"mbti": mbti}, mbti_code, slogans)
    kpi_happy = infer_kpi_happy(behavior, expression, {"chat": {"message_count": len(messages)}})

    personality = {
        "mbti": mbti,
        "sbti": sbti,
        "animal": animal,
        "tags": tags,
    }

    return {
        # ===== 完整数据层（深度报告用）=====
        "expression_dna": expression,
        "behavior_patterns": behavior,
        "personality": personality,
        # ===== 趣味推断（5 维 N 选 1 + Top 3 全展示）=====
        "sbti_top3": sbti,                    # 8 候选 Top 3 + 分数
        "animal_top3": animal["all"],         # 12 候选 Top 12 + 分数
        "decision_style": decision_style,      # 4 选 1
        "communication_style": communication_style,  # 4 选 1
        "stress_response": stress_response,    # 3 选 1
        "value_tendency": value_tendency,      # 4 选 1
        "info_processing": info_processing,    # 4 选 1
        # ===== 卡片抽象用 =====
        "slogan_candidates": slogans,
        "slogan_long": slogan_long,
        "kpi_happy": kpi_happy,
        "personality_traits": personality_traits,
        "sneaky_label": sneaky_label,
        "sbti_style": sbti_style,             # 兼容旧版（sbti_top3[0] 的人话版）
    }


def generate_slogans(
    tags: List[str],
    top_keywords: List[str],
    mbti: Dict[str, str]
) -> List[str]:
    """基于标签和关键词生成 3-5 个 slogan 候选（硬编码模板）"""
    candidates = []
    mbti_code = "".join(d[0] for d in mbti.values() if isinstance(d, str) and "(" in d)

    # 模板 1：基于 MBTI
    slogans_by_mbti = {
        "INTJ": ["看穿表象做深", "先想后做", "把复杂的事说简单"],
        "INTP": ["质疑常识", "在细节里找答案"],
        "ENTJ": ["把事推完", "目标导向", "少即是多"],
        "ENTP": ["试试看", "反对就是为了靠近真"],
        "INFJ": ["理解比表达更重要", "安静的洞察者"],
        "INFP": ["理想主义很贵", "保持真诚"],
        "ENFJ": ["把人放在第一位"],
        "ENFP": ["想到就做", "可能性优先"],
        "ISTJ": ["把事做对", "稳就是快"],
        "ISFJ": ["先照顾好你"],
        "ESTJ": ["执行大于讨论"],
        "ESFJ": ["气氛是协作的燃料"],
        "ISTP": ["工具用得熟，问题就少"],
        "ISFP": ["慢工出细活"],
        "ESTP": ["先动起来再优化"],
        "ESFP": ["现场是唯一的真相"],
    }

    if mbti_code in slogans_by_mbti:
        candidates.extend(slogans_by_mbti[mbti_code])
    else:
        candidates.extend(["做有判断力的产品", "看穿表象做深", "少即是多"])

    # 模板 2：基于 tags 增补
    if "夜猫子" in tags:
        candidates.append("深夜的安静是我的燃料")
    if "极简派" in tags:
        candidates.append("一句话能说完，就不写两句")
    if "阐释型" in tags:
        candidates.append("复杂的本质只有一条")
    if "抽象派" in tags:
        candidates.append("看见框架的人")

    # 去重
    seen = set()
    unique = []
    for s in candidates:
        if s not in seen:
            seen.add(s)
            unique.append(s)
    return unique[:5]


# ---------- CLI ----------

if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
    from collect_self import collect_all
    import argparse

    parser = argparse.ArgumentParser(description="self-distill 分析引擎")
    parser.add_argument("--days", type=int, default=30)
    args = parser.parse_args()

    from datetime import datetime, timezone, timedelta
    CST = timezone(timedelta(hours=8))
    end = datetime.now(CST)
    start = end - timedelta(days=args.days)
    end_iso = end.strftime("%Y-%m-%dT23:59:59+08:00")
    start_iso = start.strftime("%Y-%m-%dT00:00:00+08:00")
    result = collect_all(start_iso=start_iso, end_iso=end_iso)
    analysis = analyze_all(result.messages)

    # 输出到 stdout
    print(json.dumps(analysis, ensure_ascii=False, indent=2))
