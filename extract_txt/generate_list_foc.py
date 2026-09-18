#!/usr/bin/env python3
"""
generate_list.py
=========================
通过 iPlant (植物智) 的 getfoc.ashx 接口，自动生成完整物种名单，输出为 foc.py 可直接读取的 CSV。

工作原理（纯 API，无需浏览器/JS 渲染）：
  1. GET getfoc.ashx?key=Rosaceae
     -> 返回 JSON，其中 sublist 字段包含该科全部属的链接
  2. 对每个属，GET getfoc.ashx?key={Genus}
     -> 返回 JSON，其中 sublist 字段包含该属全部物种的链接
  3. 从链接 href 中提取完整学名（如 /info/Rosa acicularis?t=foc）
  4. 去重、排序、输出 CSV

"""

import requests
from bs4 import BeautifulSoup
import time
import csv
import re
import random
import urllib.parse

# ================= 配置区 =================
FAMILY_NAME = "Rosaceae"
OUTPUT_CSV = "species_list_foc.csv"
API_URL = "https://www.iplant.cn/ashx/getfoc.ashx"
SLEEP_MIN = 1.0
SLEEP_MAX = 2.5
REQUEST_TIMEOUT = 15
MAX_RETRY = 3
# ==========================================

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.iplant.cn/"
}


def fetch_foc(key):
    """调用 getfoc.ashx 接口，返回解析后的 JSON dict。"""
    params = {
        "key": key,
        "key_no": "",
        "m": str(random.random()),
    }
    for attempt in range(MAX_RETRY):
        try:
            resp = requests.get(API_URL, params=params,
                                headers=headers, timeout=REQUEST_TIMEOUT)
            resp.encoding = "utf-8"
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            print(f"    请求失败 ({attempt + 1}/{MAX_RETRY}): {e}")
        time.sleep(2)
    return None


def extract_links_from_sublist(sublist_html):
    """
    从 sublist HTML 中提取所有链接的 (text, href) 对。
    sublist 格式: <li><a href='/info/Rosa acicularis?t=foc'>R. acicularis</a> 中文名</li>
    """
    if not sublist_html:
        return []
    soup = BeautifulSoup(sublist_html, "html.parser")
    results = []
    for a in soup.find_all("a"):
        href = a.get("href", "")
        text = a.get_text(strip=True)
        if href:
            results.append((text, href))
    return results


def extract_name_from_href(href):
    """
    从 /info/Rosa acicularis?t=foc 中提取 'Rosa acicularis'。
    返回 None 如果不是物种级别的链接（如属、亚属、组等）。
    """
    # 匹配 /info/xxx?t=foc 或 /info/xxx?t=focn
    m = re.match(r"^/info/(.+?)\?t=foc", href)
    if not m:
        return None
    raw = urllib.parse.unquote(m.group(1)).strip()
    # 物种级别的名字应该是：属名 + 种加词（可能有 × 杂交符号）
    # 排除：只有属名（1个词）、含 subgen./sect.（亚属/组）
    parts = raw.split()
    if len(parts) < 2:
        return None  # 只有属名
    if any(p in ("subgen.", "sect.", "ser.", "subsect.", "subf.") for p in parts):
        return None  # 亚属、组、系等分类层级
    # 正常物种：Genus epithet  或  Genus × epithet
    return raw


def get_genera(family_name):
    """从科的接口返回中提取所有属名。"""
    print(f"[1/3] 正在获取 {family_name} 的属列表...")
    data = fetch_foc(family_name)
    if not data:
        print(f"  ❌ 获取科信息失败")
        return []

    sublist_html = data.get("sublist", "")
    links = extract_links_from_sublist(sublist_html)

    genera = []
    seen = set()
    for text, href in links:
        # 属的链接是 /info/Genus?t=foc（只有一个词）
        m = re.match(r"^/info/(.+?)\?t=foc", href)
        if m:
            name = urllib.parse.unquote(m.group(1)).strip()
            parts = name.split()
            # 属名只有一个词，且不含 subgen./sect.
            if (len(parts) == 1
                    and not any(p in name for p in ("subgen.", "sect.", "ser."))
                    and name not in seen):
                seen.add(name)
                genera.append(name)

    print(f"  ✅ 找到 {len(genera)} 个属")
    return genera


def get_species_for_genus(genus):
    """从属的接口返回中提取所有物种名。"""
    data = fetch_foc(genus)
    if not data:
        return []

    sublist_html = data.get("sublist", "")
    links = extract_links_from_sublist(sublist_html)

    species = []
    seen = set()
    for text, href in links:
        name = extract_name_from_href(href)
        if name and name not in seen:
            seen.add(name)
            species.append(name)

    return species


def main():
    print("=" * 60)
    print(f"  {FAMILY_NAME} 物种名单自动生成器 (iPlant FOC API)")
    print("=" * 60)

    # 第一步：获取所有属
    genera = get_genera(FAMILY_NAME)
    if not genera:
        print("❌ 未获取到任何属，程序退出")
        return

    # 第二步：逐个属抓取物种
    print(f"\n[2/3] 正在逐个属抓取物种（共 {len(genera)} 个属）...")
    all_species = []
    success_genera = 0

    for i, genus in enumerate(genera, 1):
        print(f"  [{i:2d}/{len(genera)}] {genus:20s} ...", end=" ")
        try:
            species = get_species_for_genus(genus)
            if species:
                print(f"✅ {len(species):3d} 种")
                all_species.extend(species)
                success_genera += 1
            else:
                print("⚠️  无物种")
        except Exception as e:
            print(f"❌ 异常: {e}")

        time.sleep(random.uniform(SLEEP_MIN, SLEEP_MAX))

    # 第三步：去重、排序、输出
    print(f"\n[3/3] 去重与输出...")
    unique_species = sorted(set(all_species))
    print(f"  原始记录:   {len(all_species)}")
    print(f"  去重后:     {len(unique_species)}")
    print(f"  有数据的属: {success_genera}/{len(genera)}")

    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["species"])
        for sp in unique_species:
            writer.writerow([sp])

    print(f"\n🎉 完成！物种名单已保存到: {OUTPUT_CSV}")
    print(f"   共 {len(unique_species)} 个物种")
    print(f"\n下一步：修改 foc.py 中的 input_csv_file = '{OUTPUT_CSV}'")
    print(f"      然后运行 python foc.py 开始批量抓取形态描述")


if __name__ == "__main__":
    main()
