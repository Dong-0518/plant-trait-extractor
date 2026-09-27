#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
植物性状提取工具 - 本地后端服务
提供物种名录查询和植物志描述抓取API
"""

from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup
import urllib.parse
import subprocess
import json
import os
import re
import time
import random

app = Flask(__name__)
CORS(app)  # 允许跨域（前端是file://打开的）

# ==================== 配置 ====================
R_SCRIPT = os.path.join(os.path.dirname(__file__), "get_species_list.R")
CONFIG_FILE = os.path.join(os.path.dirname(__file__), "server_config.json")
FOC_API_URL = "https://www.iplant.cn/ashx/getfoc.ashx"
FNA_BASE_URL = "https://floranorthamerica.org"

# 默认配置
default_config = {
    "rscript_path": "",
    "edge_path": ""
}

# 加载配置
if os.path.exists(CONFIG_FILE):
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        config = json.load(f)
else:
    config = default_config.copy()


def find_rscript():
    """自动查找Rscript.exe"""
    possible_paths = [
        "C:/Program Files/R/R-*/bin/Rscript.exe",
        "C:/Program Files (x86)/R/R-*/bin/Rscript.exe",
        "D:/R-*/bin/Rscript.exe",
        "D:/Program Files/R/R-*/bin/Rscript.exe",
        os.path.expanduser("~/AppData/Local/Programs/R/R-*/bin/Rscript.exe"),
    ]
    
    import glob
    for pattern in possible_paths:
        matches = glob.glob(pattern)
        if matches:
            matches.sort(reverse=True)
            return matches[0]
    
    return None


def find_edge():
    """自动查找Edge.exe"""
    possible_paths = [
        "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
        "C:/Program Files/Microsoft/Edge/Application/msedge.exe",
        "D:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
        "D:/Program Files/Microsoft/Edge/Application/msedge.exe",
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            return path
    
    return None


# 如果配置里没有，自动查找
if not config.get("rscript_path"):
    found = find_rscript()
    if found:
        config["rscript_path"] = found
        print(f"自动找到Rscript: {found}")
    else:
        print("⚠️ 未找到Rscript，请在设置中配置Rscript路径")

if not config.get("edge_path"):
    found = find_edge()
    if found:
        config["edge_path"] = found
        print(f"自动找到Edge: {found}")
    else:
        print("⚠️ 未找到Edge，请在设置中配置Edge路径")


def save_config():
    """保存配置到文件"""
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.iplant.cn/"
}


# ==================== 工具函数 ====================
def call_r_script(taxon_name):
    """调用R脚本，获取物种名录"""
    rscript_path = config.get("rscript_path", "")
    if not rscript_path:
        print("错误: Rscript路径未配置")
        return None
    
    try:
        result = subprocess.run(
            [rscript_path, R_SCRIPT, taxon_name],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=120
        )
        if result.returncode != 0:
            print("R脚本错误:", result.stderr)
            return None
        
        # R脚本输出JSON格式的物种列表
        data = json.loads(result.stdout.strip())
        return data.get("species", [])
    except Exception as e:
        print("调用R脚本失败:", e)
        return None


def fetch_foc_one_species(species_name):
    """抓取单个物种的FOC描述"""
    encoded_species = urllib.parse.quote(species_name)
    m_value = random.random()
    url = f"{FOC_API_URL}?key={encoded_species}&key_no=&m={m_value}"
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.encoding = 'utf-8'
        
        if response.status_code == 200:
            data = response.json()
            
            # 形态描述
            raw_description = data.get('Description', '')
            if raw_description:
                desc_text = BeautifulSoup(raw_description, 'html.parser').text
                desc_text = re.sub(r'\s+', ' ', desc_text).strip()
                desc_text = desc_text.replace('－', '-').replace('~', '-').replace('—', '-').replace('–', '-')
            else:
                desc_text = ""
            
            # 生境信息
            raw_habitat = data.get('habait', '')
            if raw_habitat:
                habitat_text = BeautifulSoup(raw_habitat, 'html.parser').text
                habitat_text = re.sub(r'\s+', ' ', habitat_text).strip()
                desc_text += "\n" + habitat_text
            
            return {
                "success": True,
                "description": desc_text,
                "source": "FOC"
            }
        else:
            return {"success": False, "error": f"HTTP {response.status_code}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def fetch_fna_one_species(species_name):
    """
    抓取单个物种的FNA描述
    需要Edge浏览器已开启CDP调试模式（端口9222）
    """
    try:
        from playwright.sync_api import sync_playwright
        
        species_url_part = species_name.replace(' ', '_')
        encoded_species = urllib.parse.quote(species_url_part)
        url = f"https://floranorthamerica.org/{encoded_species}"
        
        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp("http://localhost:9222")
            context = browser.contexts[0]
            page = context.pages[0] if context.pages else context.new_page()
            
            page.goto(url, timeout=30000)
            page.wait_for_selector('.mw-parser-output', timeout=30000)
            
            html_content = page.content()
            browser.close()
        
        soup = BeautifulSoup(html_content, 'html.parser')
        content_area = soup.find('div', class_='mw-parser-output')
        
        if content_area:
            statement_spans = content_area.find_all('span', class_='statement')
            if statement_spans:
                content_lines = [span.text.strip() for span in statement_spans if span.text.strip()]
                raw_traits_text = " ".join(content_lines)
                
                clean_text = re.sub(r'\s+', ' ', raw_traits_text).strip()
                clean_text = clean_text.replace('－', '-').replace('~', '-').replace('—', '-').replace('–', '-')
                
                return {
                    "success": True,
                    "description": clean_text,
                    "source": "FNA"
                }
            else:
                return {"success": False, "error": "未找到性状描述（statement）"}
        else:
            return {"success": False, "error": "未找到内容区块"}
            
    except Exception as e:
        error_msg = str(e)
        if "connect_over_cdp" in error_msg or "9222" in error_msg or "Connection" in error_msg:
            return {"success": False, "error": "无法连接Edge浏览器，请先开启CDP调试模式（端口9222）"}
        return {"success": False, "error": error_msg}


# ==================== API接口 ====================
@app.route('/api/species-list', methods=['GET'])
def get_species_list():
    """获取物种名录：输入科名或属名，返回该类群所有物种"""
    taxon_name = request.args.get('family', '').strip()
    if not taxon_name:
        return jsonify({"error": "请输入科名或属名"}), 400
    
    species = call_r_script(taxon_name)
    if species is None:
        return jsonify({"error": "获取物种名录失败，请检查R环境和rwcvp包是否安装"}), 500
    
    return jsonify({
        "success": True,
        "species": species,
        "count": len(species)
    })


@app.route('/api/fetch-foc', methods=['GET'])
def api_fetch_foc():
    """抓取单个物种的FOC描述"""
    species_name = request.args.get('species', '').strip()
    if not species_name:
        return jsonify({"error": "请输入物种名"}), 400
    
    result = fetch_foc_one_species(species_name)
    return jsonify(result)


@app.route('/api/fetch-fna', methods=['GET'])
def api_fetch_fna():
    """抓取单个物种的FNA描述"""
    species_name = request.args.get('species', '').strip()
    if not species_name:
        return jsonify({"error": "请输入物种名"}), 400
    
    result = fetch_fna_one_species(species_name)
    return jsonify(result)


@app.route('/api/health', methods=['GET'])
def health_check():
    """健康检查"""
    return jsonify({"status": "ok", "message": "后端服务运行中"})


@app.route('/api/get-config', methods=['GET'])
def get_config():
    """获取后端配置"""
    return jsonify({
        "rscript_path": config.get("rscript_path", ""),
        "rscript_found": bool(config.get("rscript_path", "")),
        "edge_path": config.get("edge_path", ""),
        "edge_found": bool(config.get("edge_path", ""))
    })


@app.route('/api/set-rscript', methods=['POST'])
def set_rscript():
    """设置Rscript路径"""
    data = request.get_json()
    path = data.get("path", "").strip()
    
    if not path:
        # 如果为空，自动查找
        found = find_rscript()
        if found:
            config["rscript_path"] = found
            save_config()
            return jsonify({"success": True, "path": found, "message": "自动查找成功"})
        else:
            return jsonify({"success": False, "error": "未找到Rscript，请手动输入完整路径"})
    
    # 检查路径是否存在
    if os.path.exists(path):
        config["rscript_path"] = path
        save_config()
        return jsonify({"success": True, "path": path, "message": "设置成功"})
    else:
        return jsonify({"success": False, "error": "路径不存在，请检查"})


@app.route('/api/set-edge', methods=['POST'])
def set_edge():
    """设置Edge路径"""
    data = request.get_json()
    path = data.get("path", "").strip()
    
    if not path:
        # 如果为空，自动查找
        found = find_edge()
        if found:
            config["edge_path"] = found
            save_config()
            return jsonify({"success": True, "path": found, "message": "自动查找成功"})
        else:
            return jsonify({"success": False, "error": "未找到Edge，请手动输入完整路径"})
    
    # 检查路径是否存在
    if os.path.exists(path):
        config["edge_path"] = path
        save_config()
        return jsonify({"success": True, "path": path, "message": "设置成功"})
    else:
        return jsonify({"success": False, "error": "路径不存在，请检查"})


@app.route('/api/start-edge-debug', methods=['POST'])
def start_edge_debug():
    """启动Edge调试模式"""
    edge_path = config.get("edge_path", "")
    if not edge_path:
        return jsonify({"success": False, "error": "请先配置Edge路径"})
    
    if not os.path.exists(edge_path):
        return jsonify({"success": False, "error": "Edge路径不存在，请检查"})
    
    try:
        import subprocess
        subprocess.Popen([
            edge_path,
            "--remote-debugging-port=9222",
            "--user-data-dir=C:\\temp\\edge-debug"
        ])
        return jsonify({"success": True, "message": "Edge调试模式已启动"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


# ==================== 启动 ====================
if __name__ == '__main__':
    print("=" * 50)
    print("  植物性状提取工具 - 本地后端服务")
    print("=" * 50)
    print("  服务地址: http://localhost:5000")
    print("  请保持本窗口打开，不要关闭")
    print("=" * 50)
    app.run(host='127.0.0.1', port=5000, debug=False)
