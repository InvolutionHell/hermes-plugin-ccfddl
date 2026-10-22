"""会议截稿查询：ccfddl/ccf-deadlines 的汇总数据 → 按会议名或领域列出还没截止的 DDL（北京时间）。

数据：https://ccfddl.com/conference/allconf.yml（社区维护，~680KB）。进程内缓存 6 小时，另存一份到
``$HERMES_HOME/cache/ccfddl/allconf.yml``，拉取失败时用旧的。时区写法只有 AoE / UTC±N / UTC / PT。
"""

from __future__ import annotations

import datetime as dt
import logging
import os
import re
import threading
import time
import urllib.request
from pathlib import Path
from typing import Any, Optional
from zoneinfo import ZoneInfo

try:  # the gateway's runtime venv ships ruamel.yaml, not PyYAML
    from ruamel.yaml import YAML

    def _yaml_load(raw):
        return YAML(typ="safe").load(raw)
except ImportError:  # pragma: no cover
    import yaml

    def _yaml_load(raw):
        return yaml.safe_load(raw)

logger = logging.getLogger(__name__)

DATA_URL = "https://ccfddl.com/conference/allconf.yml"
CACHE_TTL = 6 * 3600
BEIJING = dt.timezone(dt.timedelta(hours=8))
MAX_LINES = 30

# ccfddl 的 sub 代码 → 中文领域名（CCF 推荐目录的十个方向）
SUBS = {
    "AI": "人工智能", "CG": "计算机图形学与多媒体", "CT": "计算机科学理论", "DB": "数据库/数据挖掘/内容检索",
    "DS": "计算机体系结构/并行与分布计算/存储系统", "HI": "人机交互与普适计算", "MX": "交叉/综合/新兴",
    "NW": "计算机网络", "SC": "网络与信息安全", "SE": "软件工程/系统软件/程序设计语言",
}
SUB_ALIASES = {
    "人工智能": "AI", "ai": "AI", "机器学习": "AI", "nlp": "AI", "cv": "AI", "视觉": "AI",
    "图形": "CG", "图形学": "CG", "多媒体": "CG", "理论": "CT", "数据库": "DB", "数据挖掘": "DB", "信息检索": "DB",
    "体系结构": "DS", "系统": "DS", "分布式": "DS", "并行": "DS", "存储": "DS", "人机交互": "HI", "交互": "HI",
    "交叉": "MX", "综合": "MX", "网络": "NW", "计算机网络": "NW", "安全": "SC", "信息安全": "SC", "密码": "SC",
    "软件工程": "SE", "软件": "SE", "编程语言": "SE", "程序设计语言": "SE",
}

_lock = threading.Lock()
_cache: dict[str, Any] = {"at": 0.0, "data": None}


# ── data ──

def _disk_cache() -> Path:
    home = Path(os.environ.get("HERMES_HOME") or Path.home() / ".hermes")
    return home / "cache" / "ccfddl" / "allconf.yml"


def load_conferences(force: bool = False) -> list[dict]:
    with _lock:
        if not force and _cache["data"] is not None and time.time() - _cache["at"] < CACHE_TTL:
            return _cache["data"]
        path = _disk_cache()
        try:
            req = urllib.request.Request(DATA_URL, headers={"User-Agent": "hermes-ccfddl/0.1"})
            raw = urllib.request.urlopen(req, timeout=20).read()
            data = _yaml_load(raw)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
        except Exception as e:  # network / parse failure: fall back to the last good copy
            logger.warning("ccfddl: fetch failed (%s), using disk cache", e)
            if not path.exists():
                raise
            data = _yaml_load(path.read_bytes())
        _cache.update(at=time.time(), data=data or [])
        return _cache["data"]


# ── pure helpers (tested) ──

def parse_tz(name: Any) -> dt.tzinfo:
    s = str(name or "AoE").strip()
    if s.upper() in ("AOE", ""):
        return dt.timezone(dt.timedelta(hours=-12))
    if s.upper() == "PT":
        return ZoneInfo("America/Los_Angeles")
    m = re.fullmatch(r"UTC\s*([+-]\d{1,2})(?::?(\d{2}))?", s, re.I)
    if m:
        hours = int(m.group(1))
        minutes = int(m.group(2) or 0) * (1 if hours >= 0 else -1)
        return dt.timezone(dt.timedelta(hours=hours, minutes=minutes))
    if s.upper() == "UTC":
        return dt.timezone.utc
    return dt.timezone(dt.timedelta(hours=-12))  # unknown: treat like AoE (the latest plausible reading)


def parse_deadline(value: Any, tz: Any) -> Optional[dt.datetime]:
    try:
        naive = dt.datetime.strptime(str(value).strip(), "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None  # "TBD"
    return naive.replace(tzinfo=parse_tz(tz)).astimezone(BEIJING)


def ccf_label(conf: dict) -> str:
    rank = str((conf.get("rank") or {}).get("ccf") or "N").upper()
    return f"CCF-{rank if rank in ('A', 'B', 'C') else 'None'}"


def next_deadline(conf: dict, now: dt.datetime) -> Optional[dict]:
    """Earliest deadline still in the future across all years/rounds of one conference."""
    best = None
    for year in conf.get("confs") or []:
        for t in year.get("timeline") or []:
            when = parse_deadline(t.get("deadline"), year.get("timezone"))
            if when is None or when < now:
                continue
            if best is None or when < best["when"]:
                best = {"when": when, "year": year.get("year"), "comment": t.get("comment") or "",
                        "abstract": parse_deadline(t.get("abstract_deadline"), year.get("timezone")),
                        "link": year.get("link") or "", "place": year.get("place") or "", "date": year.get("date") or ""}
    return best


def resolve_sub(query: str) -> Optional[str]:
    q = query.strip()
    if q.upper() in SUBS:
        return q.upper()
    q = re.sub(r"(会议|方向|领域|类|的|ddl|DDL|截稿|截止)", "", q).strip().lower()
    if q in SUB_ALIASES:
        return SUB_ALIASES[q]
    for code, name in SUBS.items():
        if q and q in name:
            return code
    return None


def match_conferences(confs: list[dict], query: str) -> list[dict]:
    """Conference name / dblp key / words of the full name, case-insensitive. Exact title wins."""
    q = query.strip().lower()
    if not q:
        return []
    exact = [c for c in confs if str(c.get("title", "")).lower() == q or str(c.get("dblp", "")).lower() == q]
    if exact:
        return exact
    return [c for c in confs if q in str(c.get("title", "")).lower() or q in str(c.get("description", "")).lower()]


def time_left(when: dt.datetime, now: dt.datetime) -> str:
    """不到一天按小时说（「剩余 0 天」对赶稿没用）。"""
    left = when - now
    if left.days >= 1:
        return f"剩余 {left.days} 天"
    hours = int(left.total_seconds() // 3600)
    return f"剩余 {hours} 小时" if hours >= 1 else "不到 1 小时"


def fmt_line(i: int, conf: dict, d: dict, now: dt.datetime) -> str:
    return (f"{i}. {conf.get('title')} {d['year']} [{ccf_label(conf)}] - "
            f"{d['when']:%Y-%m-%d %H:%M}（{time_left(d['when'], now)}）")


_FILLER = re.compile(r"近期|最近|马上|全部|所有|能投的?|可以投的?|有哪些|会议|的|ddl|截稿|截止|时间|是什么|是啥", re.I)


def render(confs: list[dict], query: str, now: dt.datetime, rank: str = "", limit: int = MAX_LINES) -> str:
    rank = rank.strip().upper().removeprefix("CCF-")
    if not _FILLER.sub("", query).strip(" ?？"):  # 「最近能投的会议是什么」= 不限领域、按截止时间排
        query = ""
    sub = resolve_sub(query) if query.strip() else None
    if sub:
        pool, title = [c for c in confs if c.get("sub") == sub], f"{SUBS[sub]}会议 DDL（北京时间）："
    else:
        pool = match_conferences(confs, query) if query.strip() else list(confs)
        title = "会议 DDL（北京时间）：" if query.strip() else "近期会议 DDL（北京时间）："
    if rank in ("A", "B", "C"):
        pool = [c for c in pool if ccf_label(c) == f"CCF-{rank}"]
    if not pool:
        return f"没找到和「{query}」对应的会议或领域。可以输会议简称（如 CVPR、ACL），或领域（{'、'.join(SUBS.values())}）。"
    rows = sorted(((c, d) for c in pool if (d := next_deadline(c, now))), key=lambda cd: cd[1]["when"])
    if not rows:
        names = "、".join(str(c.get("title")) for c in pool[:5])
        return f"{names} 目前没有已公布、还没截止的投稿截止时间（可能还没公布，标为 TBD）。"
    lines = [title] + [fmt_line(i, c, d, now) for i, (c, d) in enumerate(rows[:limit], 1)]
    if len(rows) > limit:
        lines.append(f"……还有 {len(rows) - limit} 个，缩小范围（加 CCF 等级或换会议名）可以看全。")
    if len(rows) <= 3 and not sub:  # 查具体会议：多给一点细节
        for c, d in rows:
            extra = [f"{c.get('title')} {d['year']}：{c.get('description', '')}"]
            if d["abstract"] and d["abstract"] != d["when"]:
                extra.append(f"  摘要截止：{d['abstract']:%Y-%m-%d %H:%M}")
            if d["comment"]:
                extra.append(f"  轮次：{d['comment']}")
            if d["date"] or d["place"]:
                extra.append(f"  会期/地点：{d['date']} {d['place']}".rstrip())
            if d["link"]:
                extra.append(f"  官网：{d['link']}")
            lines += extra
    return "\n".join(lines)


# ── tool ──

SCHEMA = {
    "name": "conference_deadlines",
    "description": ("学术会议投稿截止时间（DDL）查询，数据来自 ccfddl（CCF 推荐会议等）。"
                    "query 填会议简称（CVPR、ACL、NeurIPS）或领域（人工智能、数据库、网络、安全、软件工程……），"
                    "问「最近能投哪些会」不限领域就填空字符串；"
                    "返回已排好版的北京时间列表，直接原样发给用户即可。"),
    "parameters": {"type": "object", "properties": {
        "query": {"type": "string", "description": "会议简称或领域名，如 CVPR / 人工智能 / 数据库"},
        "ccf_rank": {"type": "string", "description": "可选：只看 CCF-A / B / C"},
    }, "required": ["query"]},
}


def handle(args: dict, **kw) -> str:
    try:
        confs = load_conferences()
    except Exception as e:
        return f"会议数据暂时拿不到：{e}"
    return render(confs, str(args.get("query", "")), dt.datetime.now(BEIJING), str(args.get("ccf_rank", "")))


def register(ctx):
    ctx.register_tool(name="conference_deadlines", toolset="ccfddl", schema=SCHEMA, handler=handle, emoji="📅")
