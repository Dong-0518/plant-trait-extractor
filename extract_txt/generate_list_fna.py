#!/usr/bin/env python3
"""
从 FNA (floranorthamerica.org) 生成物种名单。

FNA 每一层级都有 "Lower Taxa" 区块（一个 div，逗号分隔的链接）。
分类层级可能很深：科→亚科→族→属→亚属→组→物种。
本脚本用递归方式下钻，只要 Lower Taxa 里的条目不是物种就继续访问，
直到拿到物种为止。加深度限制和已访问集合防止循环。

技术方式（参考 fna.py）：
  - Playwright + CDP 连接真实浏览器，绕过 Cloudflare
  - 直接解析页面 HTML 的 Lower Taxa 区块

前置条件（和 fna.py 完全一样）：
  1. "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe" --remote-debugging-port=9222
  2. 浏览器里打开 https://floranorthamerica.org 并通过 Cloudflare
  3. python generate_list_fna.py
"""

import asyncio
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
import csv
import re
import time
import urllib.parse

# ================= 配置区 =================
FAMILY_TITLE = "Rosaceae"
OUTPUT_CSV = "species_list_fna.csv"
FNA_BASE = "https://floranorthamerica.org"
SLEEP_BETWEEN_PAGES = 0.8
MAX_DEPTH = 8          # 最大递归深度
# ==========================================

# 全局：已访问的页面（防止循环），收集到的物种
visited = set()
all_species = []
page_count = 0


def is_species(title):
    """是否是物种：Genus species（排除亚种/变种/变型）"""
    title = title.strip()
    if not re.match(r"^[A-Z][a-z]+ (?:× )?[a-z][a-z\-]+$", title):
        return False
    if any(x in title for x in (" subsp. ", " var. ", " f. ", " subsp.", " var.")):
        return False
    return True


def is_hybrid_or_species(title):
    """是否是物种或杂交种（更宽松，用于收集）"""
    return is_species(title)


def title_to_url(title):
    return f"{FNA_BASE}/{urllib.parse.quote(title.replace(' ', '_'))}"


async def get_lower_taxa(page, title):
    """
    访问页面，找到 "Lower Taxa" 标题后的第一个 div，提取其中所有链接的页面标题。
    返回 (链接标题列表, 页面是否存在)
    """
    global page_count
    page_count += 1

    url = title_to_url(title)
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_selector(".mw-parser-output", timeout=20000)
        await asyncio.sleep(0.8)
        html = await page.content()
    except Exception as e:
        return [], False

    soup = BeautifulSoup(html, "html.parser")
    content = soup.find("div", class_="mw-parser-output")
    if not content:
        return [], False

    # 找到 "Lower Taxa" 标题
    lower_taxa_div = None
    for heading in content.find_all(["h2", "h3", "h4"]):
        if "Lower Taxa" in heading.get_text():
            for sib in heading.next_siblings:
                if hasattr(sib, "name") and sib.name == "div":
                    lower_taxa_div = sib
                    break
            break

    if not lower_taxa_div:
        return [], True

    # 从 href 提取页面标题（比链接文本更可靠）
    results = []
    seen = set()
    for a in lower_taxa_div.find_all("a", href=True):
        href = a["href"]
        m = re.match(r"^/([^/?#]+)", href)
        if m:
            page_title = m.group(1).replace("_", " ")
            # 跳过红链（不存在的页面）
            if "redlink=1" in href:
                continue
            if page_title and page_title not in seen:
                seen.add(page_title)
                results.append(page_title)
    return results, True


async def crawl(page, title, depth=0):
    """
    递归爬取：访问页面 → 提取 Lower Taxa → 对每个条目：
      - 如果是物种，收集
      - 否则递归下钻
    """
    global visited, all_species

    if depth > MAX_DEPTH:
        return
    if title in visited:
        return
    visited.add(title)

    indent = "  " * depth
    lower_taxa, page_exists = await get_lower_taxa(page, title)

    if not page_exists:
        print(f"{indent}⚠️  页面不存在: {title}")
        return

    if not lower_taxa:
        # 没有 Lower Taxa，可能是物种页面或末端页面
        if is_species(title):
            if title not in all_species:
                all_species.append(title)
        return

    # 分类当前页面的 Lower Taxa
    species_here = []
    taxa_to_visit = []

    for t in lower_taxa:
        if is_species(t):
            species_here.append(t)
        else:
            taxa_to_visit.append(t)

    if species_here:
        for sp in species_here:
            if sp not in all_species:
                all_species.append(sp)
        print(f"{indent}✅ {title}: {len(species_here)} 种"
              + (f" + {len(taxa_to_visit)} 个下级分类" if taxa_to_visit else ""))
    elif taxa_to_visit:
        print(f"{indent}📂 {title}: {len(taxa_to_visit)} 个下级分类")
    else:
        print(f"{indent}— {title}: 无下级分类")

    # 递归下钻非物种条目
    for t in taxa_to_visit:
        await crawl(page, t, depth + 1)


async def main():
    global all_species, visited, page_count

    print("=" * 65)
    print(f"  FNA 蔷薇科 ({FAMILY_TITLE}) 物种名单生成器")
    print(f"  方式: 递归解析 Lower Taxa 区块（科→亚科→族→属→亚属→组→种）")
    print("=" * 65)

    async with async_playwright() as p:
        print("\n正在连接真实浏览器 (CDP 9222)...")
        browser = await p.chromium.connect_over_cdp("http://localhost:9222")
        context = browser.contexts[0]
        page = context.pages[0] if context.pages else await context.new_page()

        print(f"\n开始递归爬取，从 {FAMILY_TITLE} 科页面开始...\n")
        await crawl(page, FAMILY_TITLE, depth=0)

        # 去重排序
        unique_species = sorted(set(all_species))
        print(f"\n{'='*65}")
        print(f"[汇总]")
        print(f"  访问页面数: {page_count}")
        print(f"  原始物种记录: {len(all_species)}")
        print(f"  去重后: {len(unique_species)}")
        print(f"  (FNA 官方记载: 68属, 约680种含22杂交种)")

        with open(OUTPUT_CSV, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(["species"])
            for sp in unique_species:
                writer.writerow([sp])

        print(f"\n🎉 完成！已保存到: {OUTPUT_CSV}")
        print(f"   共 {len(unique_species)} 个物种")
        print(f"\n下一步：修改 fna.py 中的 input_csv_file = '{OUTPUT_CSV}'")

        await browser.close()


if __name__ == "__main__":
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(main())
    except RuntimeError:
        asyncio.run(main())
