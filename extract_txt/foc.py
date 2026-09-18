import requests
from bs4 import BeautifulSoup
import urllib.parse
import time
import random
import csv
import os
import re

# ================= 配置区 =================
input_csv_file = 'species_list_foc.csv'  # 你的输入名单文件
output_folder = 'FloraTraiter_Data_FOC'  # 存放生成的 TXT 的文件夹名字

# 如果输出文件夹不存在，就自动创建一个
if not os.path.exists(output_folder):
    os.makedirs(output_folder)

# 伪装头
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.iplant.cn/"
}
# ==========================================

# 1. 从 CSV 文件中读取植物名单
species_list = []
try:
    # 强制使用 utf-8-sig 读取，兼容带 BOM 的 Excel 导出格式
    with open(input_csv_file, mode='r', encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        next(reader, None)  # 智能跳过第一行的表头
        for row in reader:
            if row and row[0].strip():  # 确保不是空行
                species_list.append(row[0].strip())
    print(f"成功读取了 {len(species_list)} 个物种名单，准备开工！\n")
except FileNotFoundError:
    print(f"❌ 找不到名为 {input_csv_file} 的文件，请检查是否放在了同一目录下！")
    exit()

# 2. 开始遍历抓取与数据清洗
for species in species_list:
    encoded_species = urllib.parse.quote(species)
    m_value = random.random()
    url = f"https://www.iplant.cn/ashx/getfoc.ashx?key={encoded_species}&key_no=&m={m_value}"

    print(f"正在处理: {species} ...")

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.encoding = 'utf-8'

        if response.status_code == 200:
            data = response.json()

            # 【提取一：形态描述】
            raw_description = data.get('Description', '')
            if raw_description:
                desc_text = BeautifulSoup(raw_description, 'html.parser').text
                desc_text = re.sub(r'\s+', ' ', desc_text).strip()  # 合并换行
                desc_text = desc_text.replace('－', '-').replace('~', '-').replace('—', '-').replace('–', '-')  # 统一横线
            else:
                desc_text = "未找到描述信息"

            # 【提取二：生境信息】 (注意 iPlant 接口这里的拼写是 habait)
            raw_habitat = data.get('habait', '')
            if raw_habitat:
                habitat_text = BeautifulSoup(raw_habitat, 'html.parser').text
                habitat_text = re.sub(r'\s+', ' ', habitat_text).strip()  # 生境同样合并换行
            else:
                habitat_text = "未找到生境信息"

            # 【核心组装：把学名、描述、生境拼装成一篇完整的文档】
            # 使用 \n\n 留出空行，让 NLP 程序或人眼阅读时结构更清晰
            final_content = f"{species}\n{desc_text}\n{habitat_text}"

            # 【导出步骤】
            safe_filename = species.replace(' ', '_') + '.txt'
            file_path = os.path.join(output_folder, safe_filename)

            with open(file_path, mode='w', encoding='utf-8') as txt_file:
                txt_file.write(final_content)  # 写入组装好的完整内容

            print(f"  ✅ 成功提取 (描述+生境) -> {safe_filename}")

        else:
            print(f"  ❌ {species}: 接口访问失败，状态码 {response.status_code}")

    except Exception as e:
        print(f"  ❌ {species}: 抓取时发生异常 - {e}")

    # 强制休眠 2 秒，保护服务器与 IP 安全
    time.sleep(2)

print("\n🎉 全部处理完毕！你的 NLP 纯净语料库已在文件夹中准备就绪。")