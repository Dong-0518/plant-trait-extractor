import asyncio
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
import urllib.parse
import csv
import os
import re

# ================= 配置区 =================
input_csv_file = 'species_list_fna.csv'  # 你的输入名单文件
output_folder = 'FloraTraiter_Data_FNA' # 存放生成的 TXT 的文件夹名字

if not os.path.exists(output_folder):
    os.makedirs(output_folder)


# ==========================================

async def main():
    species_list = []
    try:
        with open(input_csv_file, mode='r', encoding='utf-8-sig') as f:
            reader = csv.reader(f)
            next(reader, None)
            for row in reader:
                if row and row[0].strip():
                    species_list.append(row[0].strip())
        print(f"✅ 成功读取 {len(species_list)} 个物种，准备接管真实浏览器！\n")
    except FileNotFoundError:
        print(f"❌ 找不到名单文件！")
        return

    if not species_list:
        return

    try:
        async with async_playwright() as p:
            browser = await p.chromium.connect_over_cdp("http://localhost:9222")

            # 获取当前浏览器中已经打开的标签页
            context = browser.contexts[0]
            page = context.pages[0] if context.pages else await context.new_page()

            for species in species_list:
                species_url_part = species.replace(' ', '_')
                encoded_species = urllib.parse.quote(species_url_part)
                url = f"https://floranorthamerica.org/{encoded_species}"

                print(f"\n正在处理: {species} ...")

                try:
                    await page.goto(url)

                    # 留出 60 秒。如果弹验证码，你直接在那个真实的 Edge 窗口里点一下！
                    await page.wait_for_selector('.mw-parser-output', timeout=60000)

                    html_content = await page.content()
                    soup = BeautifulSoup(html_content, 'html.parser')

                    content_area = soup.find('div', class_='mw-parser-output')
                    if content_area:
                        statement_spans = content_area.find_all('span', class_='statement')
                        if statement_spans:
                            content_lines = [span.text.strip() for span in statement_spans if span.text.strip()]
                            raw_traits_text = " ".join(content_lines)

                            # 深度清洗逻辑
                            clean_text = re.sub(r'\s+', ' ', raw_traits_text).strip()
                            clean_text = clean_text.replace('－', '-').replace('~', '-').replace('—', '-').replace('–',
                                                                                                                  '-')
                        else:
                            clean_text = "未找到 class='statement' 的性状描述"
                    else:
                        clean_text = "未找到核心内容区块"

                    final_content = f"{species}\n{clean_text}"
                    safe_filename = species.replace(' ', '_') + '.txt'
                    file_path = os.path.join(output_folder, safe_filename)

                    with open(file_path, mode='w', encoding='utf-8') as txt_file:
                        txt_file.write(final_content)

                    print(f"  ✅ 成功提取纯正性状 -> {safe_filename}")

                except Exception as loop_e:
                    print(f"  ❌ {species}: 发生异常！可能超时或遇到验证码死循环 -> {repr(loop_e)}")

                await asyncio.sleep(2)

            print("\n🚨 列表遍历结束！已断开控制，真实浏览器保留原样。")

            # 这里只需断开连接，不用 close()，这样不会把你真实的浏览器强制关掉
            await browser.disconnect()

    except Exception as main_e:
        print(f"\n❌ 连接真实浏览器失败。请确认第一步的 cmd 命令已成功运行，且留有开了 9222 端口的浏览器！")


if __name__ == "__main__":
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(main())
    except RuntimeError:
        asyncio.run(main())