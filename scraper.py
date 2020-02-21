#!/usr/bin/env python3

# Legacy data scraper for Health Commission of Hubei Province website.
# http://wjw.hubei.gov.cn/fbjd/tzgg/index.shtml

import contextlib
import csv
import datetime
import logging
import pathlib
import re
import subprocess
import time
import urllib.parse

import bs4
import peewee
import tenacity


logging.basicConfig(format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

network_retry = tenacity.retry(
    wait=tenacity.wait_fixed(2), stop=tenacity.stop_after_attempt(3)
)

HERE = pathlib.Path(__file__).resolve().parent
database = peewee.SqliteDatabase(HERE.joinpath("data.db").as_posix())
datafile = HERE / "data.csv"
datamod = HERE / "data.py"


class DataEntry(peewee.Model):
    date = peewee.DateField(unique=True)

    total_confirmed = peewee.IntegerField(null=True)
    remaining_confirmed = peewee.IntegerField(null=True)
    remaining_severe = peewee.IntegerField(null=True)
    remaining_suspected = peewee.IntegerField(null=True)
    cured = peewee.IntegerField(null=True)
    death = peewee.IntegerField(null=True)
    new_confirmed = peewee.IntegerField(null=True)
    new_severe = peewee.IntegerField(null=True)
    new_suspected = peewee.IntegerField(null=True)
    new_cured = peewee.IntegerField(null=True)
    new_death = peewee.IntegerField(null=True)
    total_tracked = peewee.IntegerField(null=True)
    new_lifted = peewee.IntegerField(null=True)
    remaining_quarantined = peewee.IntegerField(null=True)
    hb_total_confirmed = peewee.IntegerField(null=True)
    hb_remaining_confirmed = peewee.IntegerField(null=True)
    hb_remaining_severe = peewee.IntegerField(null=True)
    hb_remaining_suspected = peewee.IntegerField(null=True)
    hb_cured = peewee.IntegerField(null=True)
    hb_death = peewee.IntegerField(null=True)
    hb_new_confirmed = peewee.IntegerField(null=True)
    hb_new_severe = peewee.IntegerField(null=True)
    hb_new_suspected = peewee.IntegerField(null=True)
    hb_new_cured = peewee.IntegerField(null=True)
    hb_new_death = peewee.IntegerField(null=True)

    article_url = peewee.TextField(unique=True)
    article_title = peewee.TextField()
    article_body = peewee.TextField()

    class Meta:
        database = database

    # Calculate remaining confirmed when official report does not
    # include this stat.
    @property
    def remaining_confirmed_calc(self):
        if self.remaining_confirmed is not None:
            return self.remaining_confirmed
        if self.cured is not None and self.death is not None:
            return self.total_confirmed - self.cured - self.death
        return None

    # Calculate new severe cases in Hubei when official report does not
    # include this stat.
    @property
    def hb_new_severe_calc(self):
        if self.hb_new_severe is not None:
            return self.hb_new_severe
        if self.hb_remaining_severe is not None:
            prev_day = self.date - datetime.timedelta(days=1)
            try:
                prev_day_entry = DataEntry.get(date=prev_day)
            except peewee.DoesNotExist:
                return None
            if prev_day_entry.hb_remaining_severe is not None:
                return self.hb_remaining_severe - prev_day_entry.hb_remaining_severe
        return None

    def __getattr__(self, name):
        if not name.startswith("not_hb_"):
            raise AttributeError
        national_attr = name[7:]
        national_val = getattr(self, national_attr)
        if national_val is None:
            try:
                national_val = getattr(self, f"{national_attr}_calc")
            except AttributeError:
                pass
        hb_attr = name[4:]
        hb_val = getattr(self, hb_attr)
        if hb_val is None:
            try:
                hb_val = getattr(self, f"{hb_attr}_calc")
            except AttributeError:
                pass
        if national_val is not None and hb_val is not None:
            return national_val - hb_val
        else:
            return None


database.create_tables([DataEntry], safe=True)


def run(cmd, capture=False):
    try:
        if capture:
            return subprocess.check_output(cmd)
        else:
            subprocess.check_call(cmd)
            return
    except subprocess.CalledProcessError as e:
        cmd_display = " ".join(cmd)
        logger.error(f"{cmd_display} failed: {e}")
        raise


@contextlib.contextmanager
def fetch_dom(url):
    logger.info(f"fetching {url}")
    run(("chrome-cli", "open", url))
    time.sleep(3)
    try:
        yield run(("chrome-cli", "source"), capture=True)
    finally:
        run(("chrome-cli", "close"))


def get_article_list(seen_urls):
    @network_retry
    def get_single_page(index_url):
        results = []
        with fetch_dom(index_url) as dom:
            soup = bs4.BeautifulSoup(dom, "html.parser")
            for a in soup.select_one(".list").select("li > a"):
                url = urllib.parse.urljoin(index_url, a["href"])
                title = a["title"]
                if title_pattern.match(title):
                    results.append((url, title))
        return results

    articles = []
    page = 1
    index_url = "http://www.nhc.gov.cn/yjb/pqt/new_list.shtml"
    while True:
        articles.extend(get_single_page(index_url))
        last_article_url, last_article_title = articles[-1]
        if (
            last_article_title == "1月21日新型冠状病毒感染的肺炎疫情情况"
            or last_article_url in seen_urls
        ):
            break
        page += 1
        index_url = f"http://www.nhc.gov.cn/yjb/pqt/new_list_{page}.shtml"
    return list(reversed(articles))


@network_retry
def get_article(url):
    with fetch_dom(url) as dom:
        s = bs4.BeautifulSoup(dom, "html.parser")
        title = s.select_one(".tit").get_text().strip()
        body_container = s.select_one("#xw_box")
        body_container.select_one(".fx").extract()
        for p in body_container.select("p[style]"):
            if "text-align: right" in p["style"].lower():
                p.extract()
        body = body_container.get_text().strip()
    print(title)
    print(body)
    return title, body


title_pattern = re.compile(r"^(?P<until>截至)?(?P<month>\d+)月(?P<day>\d+)日\w+疫情(最新)?情况$")

patterns = {
    "new_confirmed": r"新增\w*确诊(病例|患者)?(?P<new_confirmed>\d+)例",
    "hb_new_confirmed": r"(新增确诊(病例|患者)?(?P<new_confirmed>\d+)例（湖北省?(?P<hb_new_confirmed>\d+)例|^\s*湖北.*新增确诊(病例|患者)?(?P<hb_new_confirmed2>\d+)例)",
    "new_severe": r"新增重症(病例|患者)?(?P<new_severe>\d+)例",
    "hb_new_severe": r"(新增重症(病例|患者)?(?P<new_severe>\d+)例（湖北省?(?P<hb_new_severe>\d+)例|^\s*湖北.*新增重症(病例|患者)?(?P<hb_new_severe2>\d+)例)",
    "new_death": r"新增死亡(病例|患者)?(?P<new_death>\d+)例",
    "hb_new_death": r"(新增死亡(病例|患者)?(?P<new_death>\d+)例（湖北省?(?P<hb_new_death>\d+)例|^\s*湖北.*新增死亡(病例|患者)?(?P<hb_new_death2>\d+)例)",
    "new_suspected": r"新增疑似(病例|患者)?(?P<new_suspected>\d+)例",
    "hb_new_suspected": r"(新增疑似(病例|患者)?(?P<new_suspected>\d+)例（湖北省?(?P<hb_new_suspected>\d+)例|^\s*湖北.*新增疑似(病例|患者)?(?P<hb_new_suspected2>\d+)例)",
    "new_cured": r"新增治愈出院(病例|患者)?(?P<new_cured>\d+)例",
    "hb_new_cured": r"(新增治愈出院(病例|患者)?(?P<new_cured>\d+)例（湖北省?(?P<hb_new_cured>\d+)例|^\s*湖北.*新增治愈出院(病例|患者)?(?P<hb_new_cured2>\d+)例)",
    "new_lifted": r"解除医学观察(的密切接触者)?(?P<new_lifted>\d+)人",
    "remaining_confirmed": r"现有确诊(病例|患者)?(?P<remaining_confirmed>\d+)例",
    "hb_remaining_confirmed": r"^\s*湖北.*现有确诊(病例|患者)?(?P<hb_remaining_confirmed>\d+)例",
    "remaining_severe": r"(?<!新增)重症(病例|患者)?(?P<remaining_severe>\d+)例",
    "hb_remaining_severe": r"^\s*湖北.*(?<!新增)重症(病例|患者)?(?P<hb_remaining_severe>\d+)例",
    "cured": r"(?<!新增)治愈出院(病例|患者)?(?P<cured>\d+)例",
    "hb_cured": r"^\s*湖北.*(?<!新增)治愈出院(病例|患者)?(?P<hb_cured>\d+)例",
    "death": r"(?<!新增)死亡(病例|患者)?(?P<death>\d+)例",
    "hb_death": r"^\s*湖北.*(?<!新增)死亡(病例|患者)?(?P<hb_death>\d+)例",
    "total_confirmed": r"累计(报告)?\w*确诊(病例|患者)?(?P<total_confirmed>\d+)例",
    "hb_total_confirmed": r"^\s*湖北.*累计(报告)?\w*确诊(病例|患者)?(?P<hb_total_confirmed>\d+)例",
    "remaining_suspected": r"(现有|共有|累计报告)疑似(病例|患者)?(?P<remaining_suspected>\d+)例",
    "hb_remaining_suspected": r"^\s*湖北.*(现有|共有|累计报告)疑似(病例|患者)?(?P<hb_remaining_suspected>\d+)例",
    "total_tracked": r"追踪到密切接触者(?P<total_tracked>\d+)人",
    "remaining_quarantined": r"(尚在医学观察的密切接触者(?P<remaining_quarantined>\d+)人|(?P<remaining_quarantined2>\d+)人正在接受医学观察)",
}

negative_patterns = {
    "new_severe": r"重症(病例|患者)减少(?P<new_severe>\d+)例",
}

introduced = {
    "new_death": "01-21",
    "death": "01-21",
    "remaining_severe": "01-21",
    "new_cured": "01-23",
    "cured": "01-23",
    "new_severe": "01-25",
    "hb_new_death": "01-25",
    "hb_new_confirmed": "02-01",
    "hb_new_severe": "02-01",
    "hb_new_suspected": "02-01",
    "hb_new_cured": "02-01",
    "remaining_confirmed": "02-06",
    "hb_total_confirmed": "02-12",
    "hb_remaining_confirmed": "02-12",
    "hb_remaining_severe": "02-12",
    "hb_remaining_suspected": "02-12",
    "hb_cured": "02-12",
    "hb_death": "02-12",
}


def parse_article(title, body):
    m = title_pattern.match(title)
    month = int(m["month"])
    day = int(m["day"])
    if not m["until"]:
        # Date in the title is the reporting date, not the reported date.
        # It's safe to subtract 1 from the day since we know all instances.
        day -= 1
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
        elif category in negative_patterns and (
            m := re.search(negative_patterns[category], body, re.M)
        ):
            if m[category]:
                count = -int(m[category])
            else:
                count = -int(m[f"{category}2"])
            data[category] = count
            print(f"{count}\t{category}")
            continue
        if category in introduced and date_str < introduced[category]:
            continue
        logger.critical(f"{date}: no match for {category}: {pattern!r}")
    return data


def main():
    recorded_urls = set(entry.article_url for entry in DataEntry.select())
    articles = get_article_list(recorded_urls)
    for url, _ in articles:
        if url in recorded_urls:
            continue
        title, body = get_article(url)
        data = parse_article(title, body)
        data.update(
            article_url=url, article_title=title, article_body=body,
        )
        DataEntry.create(**data)

    with datafile.open("w") as fp:
        writer = csv.writer(fp)
        writer.writerow(
            [
                "日期",
                "累计确诊",
                "当前确诊",
                "当前重症",
                "当前疑似",
                "治愈",
                "死亡",
                "新确诊",
                "新重症",
                "新疑似",
                "新治愈",
                "新死亡",
                "累计追踪",
                "新排除",
                "当前观察",
                "湖北累计确诊",
                "湖北当前确诊",
                "湖北当前重症",
                "湖北当前疑似",
                "湖北治愈",
                "湖北死亡",
                "湖北新确诊",
                "湖北新重症",
                "湖北新疑似",
                "湖北新治愈",
                "湖北新死亡",
                "非湖北累计确诊",
                "非湖北当前确诊",
                "非湖北当前重症",
                "非湖北当前疑似",
                "非湖北治愈",
                "非湖北死亡",
                "非湖北新确诊",
                "非湖北新重症",
                "非湖北新疑似",
                "非湖北新治愈",
                "非湖北新死亡",
            ]
        )
        for entry in list(DataEntry.select().order_by(DataEntry.date)):
            writer.writerow(
                [
                    entry.date.strftime("%Y-%m-%d"),
                    entry.total_confirmed,
                    entry.remaining_confirmed_calc,
                    entry.remaining_severe,
                    entry.remaining_suspected,
                    entry.cured,
                    entry.death,
                    entry.new_confirmed,
                    entry.new_severe,
                    entry.new_suspected,
                    entry.new_cured,
                    entry.new_death,
                    entry.total_tracked,
                    entry.new_lifted,
                    entry.remaining_quarantined,
                    entry.hb_total_confirmed,
                    entry.hb_remaining_confirmed,
                    entry.hb_remaining_severe,
                    entry.hb_remaining_suspected,
                    entry.hb_cured,
                    entry.hb_death,
                    entry.hb_new_confirmed,
                    entry.hb_new_severe_calc,
                    entry.hb_new_suspected,
                    entry.hb_new_cured,
                    entry.hb_new_death,
                    entry.not_hb_total_confirmed,
                    entry.not_hb_remaining_confirmed,
                    entry.not_hb_remaining_severe,
                    entry.not_hb_remaining_suspected,
                    entry.not_hb_cured,
                    entry.not_hb_death,
                    entry.not_hb_new_confirmed,
                    entry.not_hb_new_severe,
                    entry.not_hb_new_suspected,
                    entry.not_hb_new_cured,
                    entry.not_hb_new_death,
                ]
            )


if __name__ == "__main__":
    main()
