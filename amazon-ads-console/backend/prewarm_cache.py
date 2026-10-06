from __future__ import annotations

import json
import os
import time

import run_rds  # noqa: F401 - loads the production RDS environment.
from app.services.build_cache import build_cache
from app.services.operator_cpo import operator_cpo_summary, operator_period_options


def main() -> None:
    started = time.perf_counter()
    periods = operator_period_options()
    daily = periods.get("daily") or []
    count = max(1, int(os.getenv("CPO_PREWARM_DAYS", "7")))
    warmed: list[str] = []
    for option in daily[:count]:
        day = option.get("value")
        if not day:
            continue
        operator_cpo_summary(day, "daily")
        warmed.append(day)
    print(json.dumps({
        "ok": True,
        "latestDate": periods.get("latestDate"),
        "warmedDates": warmed,
        "elapsed": round(time.perf_counter() - started, 3),
        "redis": build_cache.stats(),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
