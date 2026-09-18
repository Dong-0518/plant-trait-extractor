# 植物形态描述批量抓取工具

从 **中国植物志 (FOC/iPlant)** 和 **北美植物志 (FNA)** 批量抓取蔷薇科植物的形态描述文本，并提供一个基于浏览器的性状提取工具。

## 项目结构

```
├── foc.py                          # FOC/iPlant 批量抓取（requests）
├── fna.py                          # FNA 批量抓取（Playwright + CDP，绕 Cloudflare）
├── generate_list_fna.py  # FNA 物种名单生成（递归爬取 Lower Taxa）
├── check_missing.py                # 缺失物种检查与补充名单生成
├── species_list_foc.csv       # FOC 物种名单
├── species_list_fna.csv   # FNA 物种名单
├── 提取.html                       # 植物性状提取工具（纯前端浏览器应用）
├── requirements.txt                # Python 依赖
└── README.md
```

## 环境要求

- Python 3.9+
- Edge 浏览器（用于 FNA 的 CDP 连接）
- 安装依赖：

```bash
pip install -r requirements.txt
playwright install chromium
```

## 使用流程

### 第一步：生成物种名单

**FNA 名单**（递归爬取 FNA 网站的 Lower Taxa）：

```bash
# 先启动 Edge 并开启调试端口
"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" --remote-debugging-port=9222

# 在浏览器中打开 https://floranorthamerica.org 并通过 Cloudflare 验证
python generate_list_fna.py
```

输出：`species_list_fna.csv`

**FOC 名单**（调用 iPlant getfoc.ashx 接口）：

```bash
python generate_list_foc.py
```

输出：`species_list_foc.csv`

### 第二步：批量抓取形态描述

**FNA 抓取**：

```bash
# 确保 Edge CDP 浏览器已打开并通过 Cloudflare
python fna.py
```

- 读取 `species_list_fna.csv`
- 逐个访问 FNA 物种页面，提取 `span.statement` 性状描述
- 输出到 `FloraTraiter_Data_FNA/`，每个物种一个 txt 文件

**FOC 抓取**：

```bash
python foc.py
```

- 读取 `species_list_foc.csv`
- 调用 iPlant API 抓取描述和生境
- 输出到 `FloraTraiter_Data_FOC/`

### 第三步：补充抓取遗漏物种

遇到 Cloudflare 人机验证时，部分物种会被跳过。抓取完成后检查：

```bash
python check_missing.py --fix
```

会生成 `species_list_fna_missing.csv`，把 `fna.py` 中的 `input_csv_file` 改为这个文件，重新运行即可。反复迭代直到缺失为 0。

### 第四步：性状提取

打开 `提取.html`（双击即可在浏览器中运行）：

1. **导入 CSV** 定义性状字段
2. **批量导入 TXT**（抓取好的描述文本）
3. 配置 AI API（OpenAI 兼容，如豆包/火山引擎）
4. 自动提取或手动划词填入字段
5. **导出 Excel**

## 注意事项

- FNA 有 Cloudflare 防护，必须通过 CDP 连接真实浏览器，不能用纯 requests
- 抓取间隔建议 1-2 秒，避免被封
- 遇到人机验证时，在 Edge 浏览器窗口手动完成验证后脚本会继续
