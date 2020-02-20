#!/usr/bin/env python3

import datetime
import re
import sys

import bs4

from scraper import logger, network_retry, fetch_dom, DataEntry


@network_retry
def get_article(url):
    with fetch_dom(url) as dom:
        s = bs4.BeautifulSoup(dom, "html.parser")
        body = s.select_one("#article-box").get_text().strip()
    print(body)
    return body


date_pattern = re.compile(r"^\s*2020年(?P<month>\d+)月(?P<day>\d+)日0时?(-|—)24时")

patterns = {
    "hb_new_confirmed": r"新增\w+病例(?P<hb_new_confirmed>\d+)例",
    "hb_new_death": r"新增(死亡|病亡)(病例)?(?P<hb_new_death>\d+)例",
    "hb_new_cured": r"新增出院(病例)?(?P<hb_new_cured>\d+)例",
    "hb_remaining_severe": r"(?<!危)重症(病例)?(?P<hb_remaining_severe>\d+)例",
    "hb_remaining_critical": r"危重症(病例)?(?P<hb_remaining_critical>\d+)例",
    "hb_cured": r"(?<!新增)出院(病例)?(?P<hb_cured>\d+)例",
    "hb_death": r"(?<!新增)(死亡|病亡)(病例)?(?P<hb_death>\d+)例",
    "hb_total_confirmed": r"累计报告\w+病例(?P<hb_total_confirmed>\d+)例",
    "hb_remaining_suspected": r"现有疑似病例(?P<hb_remaining_suspected>\d+)(例|人)",
}

introduced = {
    "hb_new_cured": "01-29",
    "hb_remaining_suspected": "02-08",
}


def parse_article(body):
    m = date_pattern.match(body)
    month = int(m["month"])
    day = int(m["day"])
    date = datetime.date(2020, month, day)
    date_str = f"{month:02}-{day:02}"
    print(date_str)
    data = dict(date=date)
    for category, pattern in patterns.items():
        if m := re.search(pattern, body, re.M):
            if m[category]:
                count = int(m[category])
            else:
                count = int(m[f"{category}2"])
            data[category] = count
            print(f"{count}\t{category}")
            continue
        if category in introduced and date_str < introduced[category]:
            continue
        logger.critical(f"{date}: no match for {category}: {pattern!r}")
    if "hb_remaining_critical" in data:
        data["hb_remaining_severe"] += data["hb_remaining_critical"]
        del data["hb_remaining_critical"]
        print(
            f"{data['hb_remaining_severe']}\thb_remainig_severe + hb_remaining_critical"
        )
    else:
        del data["hb_remaining_severe"]
    if all(k in data for k in ("hb_total_confirmed", "hb_cured", "hb_death")):
        data["hb_remaining_confirmed"] = (
            data["hb_total_confirmed"] - data["hb_cured"] - data["hb_death"]
        )
    return data


def main():
    for url in (
        "http://wjw.hubei.gov.cn/fbjd/dtyw/202002/t20200212_2024650.shtml",  # 02-11
        "http://wjw.hubei.gov.cn/fbjd/tzgg/202002/t20200211_2023521.shtml",  # 02-10
        "http://wjw.hubei.gov.cn/fbjd/tzgg/202002/t20200210_2022515.shtml",  # 02-09
        "http://wjw.hubei.gov.cn/fbjd/tzgg/202002/t20200209_2021933.shtml",  # 02-08
        "http://wjw.hubei.gov.cn/fbjd/tzgg/202002/t20200208_2021419.shtml",  # 02-07
        "http://wjw.hubei.gov.cn/fbjd/tzgg/202002/t20200207_2020606.shtml",  # 02-06
        "http://wjw.hubei.gov.cn/fbjd/tzgg/202002/t20200206_2019848.shtml",  # 02-05
        "http://wjw.hubei.gov.cn/fbjd/tzgg/202002/t20200205_2019294.shtml",  # 02-04
        "http://wjw.hubei.gov.cn/fbjd/tzgg/202002/t20200204_2018743.shtml",  # 02-03
        "http://wjw.hubei.gov.cn/fbjd/tzgg/202002/t20200203_2018273.shtml",  # 02-02
        "http://wjw.hubei.gov.cn/fbjd/tzgg/202002/t20200202_2017659.shtml",  # 02-01
        "http://wjw.hubei.gov.cn/fbjd/tzgg/202002/t20200201_2017101.shtml",  # 01-31
        "http://wjw.hubei.gov.cn/fbjd/tzgg/202001/t20200131_2016681.shtml",  # 01-30
        "http://wjw.hubei.gov.cn/fbjd/tzgg/202001/t20200130_2016306.shtml",  # 01-29
        "http://wjw.hubei.gov.cn/fbjd/tzgg/202001/t20200129_2016108.shtml",  # 01-28
        "http://wjw.hubei.gov.cn/fbjd/tzgg/202001/t20200129_2016107.shtml",  # 01-27
        "http://wjw.hubei.gov.cn/fbjd/tzgg/202001/t20200129_2016119.shtml",  # 01-26
        "http://wjw.hubei.gov.cn/fbjd/tzgg/202001/t20200129_2016112.shtml",  # 01-25
        "http://wjw.hubei.gov.cn/fbjd/tzgg/202001/t20200125_2014856.shtml",  # 01-24
        "http://wjw.hubei.gov.cn/fbjd/dtyw/202001/t20200124_2014626.shtml",  # 01-23
    ):
        body = get_article(url)
        data = parse_article(body)
        date = data["date"]
        print(data)
        entry = DataEntry.get(date=date)
        for key in patterns:
            if key == "hb_remaining_critical":
                continue
            val = data.get(key)
            existing_val = getattr(entry, key)
            if existing_val is not None and val is not None and existing_val != val:
                logger.critical(
                    f"{date} {key} discrepancy: NHC value {existing_val}, Hubei HC value {val}"
                )
                sys.exit(1)
        DataEntry.update(**data).where(DataEntry.date == date).execute()


if __name__ == "__main__":
    main()
