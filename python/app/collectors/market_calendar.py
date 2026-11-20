
from datetime import datetime, time
from zoneinfo import ZoneInfo

import exchange_calendars as xcals

JST = ZoneInfo("Asia/Tokyo")


def is_tse_business_day(target_date):
    """東京証券取引所の営業日か判定"""
    calendar = xcals.get_calendar("XTKS")
    return bool(calendar.is_session(target_date.isoformat()))


def can_run_daily_update(target_date, now=None):
    """指定日の株価自動更新を開始できるか判定"""
    if now is None:
        now = datetime.now(JST)
    else:
        now = now.astimezone(JST)

    if not is_tse_business_day(target_date):
        return False

    if target_date != now.date():
        return False

    return now.time() >= time(18, 0)

from datetime import timedelta


def previous_tse_business_day(today):
    """指定日より前の東証営業日を取得する"""
    calendar = xcals.get_calendar("XTKS")

    day = today - timedelta(days=1)

    for _ in range(14):
        if calendar.is_session(day.isoformat()):
            return day

        day -= timedelta(days=1)

    raise RuntimeError("過去14日以内に東証営業日が見つかりません")