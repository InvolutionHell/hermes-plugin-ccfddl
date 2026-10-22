"""ccfddl 插件：时区换算、下一个截止、领域/会议名匹配、排版。纯函数，不联网。"""
import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import tool as T  # noqa: E402

NOW = dt.datetime(2026, 10, 17, 12, 0, tzinfo=T.BEIJING)
CONFS = [
    {"title": "CVPR", "description": "IEEE/CVF Conference on Computer Vision and Pattern Recognition", "sub": "AI",
     "rank": {"ccf": "A"}, "dblp": "cvpr", "confs": [
         {"year": 2026, "timezone": "UTC-12", "timeline": [{"deadline": "2025-11-13 23:59:59"}]},
         {"year": 2027, "timezone": "UTC-12", "link": "https://cvpr.example/2027", "date": "June 2027", "place": "Seattle",
          "timeline": [{"abstract_deadline": "2026-11-10 23:59:59", "deadline": "2026-11-16 23:59:59"}]}]},
    {"title": "ESANN", "description": "European Symposium on ANN", "sub": "AI", "rank": {"ccf": "N"},
     "confs": [{"year": 2027, "timezone": "UTC-8", "timeline": [{"deadline": "2026-11-18 23:59:59"}]}]},
    {"title": "SIGMOD", "description": "ACM SIGMOD Conference", "sub": "DB", "rank": {"ccf": "A"},
     "confs": [{"year": 2027, "timezone": "AoE", "timeline": [{"deadline": "TBD"}]}]},
    {"title": "OSDI", "description": "Operating Systems Design and Implementation", "sub": "DS", "rank": {"ccf": "A"},
     "confs": [{"year": 2027, "timezone": "PT", "timeline": [{"deadline": "2026-12-10 17:00:00"}]}]},
]


def test_timezones_to_beijing():
    assert T.parse_deadline("2026-11-16 23:59:59", "UTC-12") == dt.datetime(2026, 11, 17, 19, 59, 59, tzinfo=T.BEIJING)
    assert T.parse_deadline("2026-11-16 23:59:59", "AoE").hour == 19
    assert T.parse_deadline("2026-11-18 23:59:59", "UTC-8").strftime("%m-%d %H:%M") == "11-19 15:59"
    assert T.parse_deadline("2026-12-10 17:00:00", "PT").strftime("%m-%d %H:%M") == "12-11 09:00"  # PST = UTC-8
    assert T.parse_deadline("2026-07-10 17:00:00", "PT").strftime("%m-%d %H:%M") == "07-11 08:00"  # PDT = UTC-7
    assert T.parse_deadline("2026-11-16 12:00:00", "UTC").hour == 20
    assert T.parse_deadline("TBD", "AoE") is None


def test_render_category_matches_requested_format():
    out = T.render(CONFS, "人工智能", NOW)
    assert out.splitlines() == [
        "人工智能会议 DDL（北京时间）：",
        "1. CVPR 2027 [CCF-A] - 2026-11-17 19:59（剩余 31 天）",
        "2. ESANN 2027 [CCF-None] - 2026-11-19 15:59（剩余 33 天）",
    ]
    assert T.render(CONFS, "AI", NOW) == out and T.render(CONFS, "人工智能会议ddl", NOW) == out


def test_under_a_day_shows_hours():
    when = dt.datetime(2026, 10, 18, 6, 30, tzinfo=T.BEIJING)
    assert T.time_left(when, NOW) == "剩余 18 小时"
    assert T.time_left(NOW + dt.timedelta(minutes=20), NOW) == "不到 1 小时"
    assert T.time_left(NOW + dt.timedelta(days=1, hours=5), NOW) == "剩余 1 天"


def test_render_single_conference_adds_details_and_skips_past_years():
    out = T.render(CONFS, "cvpr", NOW)
    assert "1. CVPR 2027 [CCF-A] - 2026-11-17 19:59（剩余 31 天）" in out
    assert "摘要截止：2026-11-11 19:59" in out and "官网：https://cvpr.example/2027" in out


def test_tbd_unknown_and_rank_filter():
    assert "TBD" in T.render(CONFS, "SIGMOD", NOW)
    assert T.render(CONFS, "不存在的会", NOW).startswith("没找到")
    assert T.render(CONFS, "近期最近能投的会议是什么", NOW) == T.render(CONFS, "", NOW)
    assert T.render(CONFS, "", NOW).startswith("近期会议 DDL")
    assert "ESANN" not in T.render(CONFS, "人工智能", NOW, rank="CCF-A")


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
    print("ok")
