#!/usr/bin/env python3
"""Schedule Jenkins test releases from the release workbook.

Credentials are read from JENKINS_USER and JENKINS_PASSWORD (or
JENKINS_API_TOKEN). The script is dry-run by default; use --execute to build.
"""

import argparse
import base64
import datetime as dt
import getpass
import http.cookiejar
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
import xml.etree.ElementTree as ET


DEFAULT_XLSX = "/Users/mured/Downloads/发布测试文档.xlsx"
DEFAULT_JENKINS = "https://jenkins-test.ikcrm.com/jenkins"
JOB_MAP = {
    "Pipeline Test-crm-h5-ding-mobile": "Test-crm-h5-ding-mobile",
    "Pipeline Test-crm-h5-lixiao-mobile": "Test-crm-h5-lixiao-mobile",
    "Pipeline Test-ik-crm-h5-hybrid-lx-duli": "Test-ik-crm-h5-hybrid-lx-duli",
}


def local_name(tag):
    return tag.rsplit("}", 1)[-1]


def parse_workbook(path):
    """Read the small release table with only Python's standard library."""
    ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    with zipfile.ZipFile(path) as book:
        shared = []
        if "xl/sharedStrings.xml" in book.namelist():
            root = ET.fromstring(book.read("xl/sharedStrings.xml"))
            for si in root:
                shared.append("".join(t.text or "" for t in si.iter() if local_name(t.tag) == "t"))
        sheet_path = "xl/worksheets/sheet1.xml"
        root = ET.fromstring(book.read(sheet_path))
        cells = {}
        for cell in root.findall(".//m:c", ns):
            ref = cell.attrib.get("r", "")
            value_node = cell.find("m:v", ns)
            value = "" if value_node is None else (value_node.text or "")
            if cell.attrib.get("t") == "s" and value:
                value = shared[int(value)]
            cells[ref] = value

    rows = []
    for row in range(20, 23):
        project = cells.get(f"A{row}", "").strip()
        job_label = cells.get(f"C{row}", "").strip()
        branch = cells.get(f"D{row}", "").strip() or "test"
        release_time = cells.get(f"G{row}", "").strip()
        if not project and not job_label:
            continue
        if not release_time:
            raise ValueError(f"第 {row} 行没有发布时间")
        try:
            fraction = float(release_time)
            if 0 <= fraction < 1:
                seconds = round(fraction * 24 * 60 * 60)
                release_time = f"{seconds // 3600:02d}:{(seconds % 3600) // 60:02d}"
        except ValueError:
            pass
        rows.append({"row": row, "project": project, "job_label": job_label,
                     "branch": branch, "release_time": release_time})
    if not rows:
        raise ValueError("未找到 A20:G22 发布项目记录")
    return rows


class Jenkins:
    def __init__(self, base_url, user, secret):
        self.base = base_url.rstrip("/")
        token = base64.b64encode(f"{user}:{secret}".encode()).decode()
        self.headers = {"Authorization": f"Basic {token}", "User-Agent": "release-scheduler/1.0"}
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))
        self.crumb = None

    def request(self, path, method="GET", data=None, extra_headers=None):
        headers = dict(self.headers)
        headers.update(extra_headers or {})
        req = urllib.request.Request(self.base + path, data=data, headers=headers, method=method)
        try:
            return self.opener.open(req, timeout=30)
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", "replace")[:500]
            raise RuntimeError(f"Jenkins HTTP {exc.code}: {body}") from exc

    def get_json(self, path):
        with self.request(path) as response:
            return __import__("json").load(response)

    def prepare_crumb(self):
        try:
            self.crumb = self.get_json("/crumbIssuer/api/json")
        except RuntimeError as exc:
            if "HTTP 404" not in str(exc):
                raise

    def job_info(self, job):
        return self.get_json("/job/" + urllib.parse.quote(job, safe="") + "/api/json")

    def trigger(self, job, params):
        path = "/job/" + urllib.parse.quote(job, safe="") + "/buildWithParameters"
        encoded = urllib.parse.urlencode(params).encode()
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        if self.crumb:
            headers[self.crumb["crumbRequestField"]] = self.crumb["crumb"]
        with self.request(path, method="POST", data=encoded, extra_headers=headers) as response:
            queue_url = response.headers.get("Location")
        if not queue_url:
            raise RuntimeError(f"Jenkins 未返回队列地址: {job}")
        return queue_url.rstrip("/")

    def wait_for_build(self, queue_url):
        queue_api = queue_url + "/api/json"
        for _ in range(180):
            with self.opener.open(urllib.request.Request(queue_api, headers=self.headers), timeout=30) as response:
                item = __import__("json").load(response)
            if item.get("cancelled"):
                raise RuntimeError("Jenkins 队列项目被取消")
            if item.get("executable"):
                return item["executable"]["url"].rstrip("/")
            time.sleep(5)
        raise TimeoutError("等待 Jenkins 队列超过 15 分钟")

    def wait_for_result(self, build_url):
        for _ in range(720):
            with self.opener.open(urllib.request.Request(build_url + "/api/json", headers=self.headers), timeout=30) as response:
                build = __import__("json").load(response)
            if not build.get("building"):
                return build.get("result"), build.get("url", build_url)
            time.sleep(5)
        raise TimeoutError("等待 Jenkins 构建超过 60 分钟")


def main():
    parser = argparse.ArgumentParser(description="按 Excel 发布时间执行 Jenkins 测试发布")
    parser.add_argument("--xlsx", default=os.getenv("RELEASE_XLSX", DEFAULT_XLSX))
    parser.add_argument("--date", help="发布日期，格式 YYYY-MM-DD；默认今天")
    parser.add_argument("--execute", action="store_true", help="真正触发 Jenkins；默认仅预检")
    args = parser.parse_args()

    rows = parse_workbook(args.xlsx)
    base_url = os.getenv("JENKINS_URL", DEFAULT_JENKINS)
    user = os.getenv("JENKINS_USER")
    secret = os.getenv("JENKINS_API_TOKEN") or os.getenv("JENKINS_PASSWORD")
    if args.execute and (not user or not secret):
        raise RuntimeError("执行发布需要设置 JENKINS_USER 和 JENKINS_API_TOKEN/JENKINS_PASSWORD")

    today = dt.date.today()
    target_date = dt.date.fromisoformat(args.date) if args.date else today
    jobs = []
    for row in rows:
        job = JOB_MAP.get(row["job_label"], row["job_label"].removeprefix("Pipeline "))
        if not job.startswith("Test-"):
            raise ValueError(f"无法映射 Jenkins Job: {row['job_label']}")
        hour, minute = map(int, row["release_time"].split(":")[:2])
        target = dt.datetime.combine(target_date, dt.time(hour, minute))
        jobs.append((row, job, target))

    now = dt.datetime.now()
    first_target = min(item[2] for item in jobs)
    print(f"Excel: {args.xlsx}")
    for row, job, target in jobs:
        print(f"第 {row['row']} 行: {row['project']} -> {job}, branch={row['branch']}, at={target:%Y-%m-%d %H:%M}")
    if not args.execute:
        print("预检完成，未触发 Jenkins。确认无误后加 --execute 执行。")
        return
    if first_target <= now:
        raise RuntimeError(f"发布时间 {first_target:%Y-%m-%d %H:%M} 已到或已过，拒绝立即发布；请使用 --date 指定未来日期")

    client = Jenkins(base_url, user, secret)
    client.prepare_crumb()
    for row, job, target in jobs:
        info = client.job_info(job)
        if not info.get("buildable"):
            raise RuntimeError(f"Job 不可构建: {job}")
    wait_seconds = (first_target - dt.datetime.now()).total_seconds()
    print(f"已通过 Job 预检，将等待 {wait_seconds:.0f} 秒后开始顺序发布。")
    time.sleep(wait_seconds)

    subject = os.getenv("JENKINS_DEPLOY_SUBJECT", "")
    for row, job, _ in jobs:
        params = {
            "Deployflag": "Deploy", "gitbranch": row["branch"], "SonarQube": "False",
            "isPost": "false", "deploysubject": subject, "Mode": "Test", "TL": "1",
            "emails": os.getenv("JENKINS_EMAILS", "wanglongjs@lixiaoyun.com"),
            "SERVER_IP": os.getenv("JENKINS_SERVER_IP", "47.104.184.66"),
        }
        queue = client.trigger(job, params)
        build = client.wait_for_build(queue)
        result, url = client.wait_for_result(build)
        print(f"{job}: {result} {url}")
        if result != "SUCCESS":
            raise RuntimeError(f"发布失败，停止后续 Job: {job}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("已取消。", file=sys.stderr)
        sys.exit(130)
    except Exception as exc:
        print(f"错误: {exc}", file=sys.stderr)
        sys.exit(1)
