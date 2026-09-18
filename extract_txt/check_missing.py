#!/usr/bin/env python3
"""
check_missing.py
================
对比物种名单 CSV 和输出目录中的 txt 文件，找出抓取失败/缺失的物种，
生成缺失物种名单，供 fna.py / foc.py 重新抓取。

用法：
  python check_missing.py                          # 检查 FNA
  python check_missing.py --source foc             # 检查中国植物志
  python check_missing.py --source fna --fix       # 检查并生成缺失名单 CSV
"""

import csv
import os
import argparse
import sys

# ================= 配置区 =================
CONFIG = {
    "fna": {
        "input_csv": "species_list_rosaceae_fna.csv",
        "output_folder": "FloraTraiter_Data_FNA_rosaceae",
        "missing_csv": "species_list_rosaceae_fna_missing.csv",
        "label": "FNA (北美植物志)",
    },
    "foc": {
        "input_csv": "species_list_rosaceae.csv",
        "output_folder": "FloraTraiter_Data",
        "missing_csv": "species_list_rosaceae_foc_missing.csv",
        "label": "中国植物志 (FOC/iPlant)",
    },
}
# ==========================================


def species_to_filename(species):
    """物种名 → 输出文件名（空格换下划线 + .txt）"""
    return species.replace(" ", "_") + ".txt"


def check(source, generate_missing=False):
    cfg = CONFIG[source]
    input_csv = cfg["input_csv"]
    output_folder = cfg["output_folder"]
    missing_csv = cfg["missing_csv"]
    label = cfg["label"]

    print("=" * 65)
    print(f"  抓取完整性检查: {label}")
    print("=" * 65)

    # 1. 读取物种名单
    if not os.path.exists(input_csv):
        print(f"❌ 找不到名单文件: {input_csv}")
        return

    species_list = []
    with open(input_csv, mode="r", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        next(reader, None)  # 跳过表头
        for row in reader:
            if row and row[0].strip():
                species_list.append(row[0].strip())

    print(f"\n📋 名单物种数: {len(species_list)}")

    # 2. 扫描输出目录
    if not os.path.exists(output_folder):
        print(f"❌ 找不到输出目录: {output_folder}")
        return

    existing_files = set(os.listdir(output_folder))
    print(f"📁 输出目录文件数: {len(existing_files)}")

    # 3. 对比找出缺失
    missing = []
    empty_or_bad = []
    for species in species_list:
        filename = species_to_filename(species)
        if filename not in existing_files:
            missing.append(species)
        else:
            # 检查文件是否有实质内容
            filepath = os.path.join(output_folder, filename)
            try:
                size = os.path.getsize(filepath)
                if size < 50:  # 太小可能是抓取失败的占位
                    empty_or_bad.append((species, size))
            except OSError:
                empty_or_bad.append((species, -1))

    # 4. 输出统计
    success_count = len(species_list) - len(missing)
    print(f"\n{'='*65}")
    print(f"  统计结果")
    print(f"{'='*65}")
    print(f"  ✅ 已抓取: {success_count}/{len(species_list)} ({100*success_count/len(species_list):.1f}%)")
    print(f"  ❌ 缺失:   {len(missing)}")
    if empty_or_bad:
        print(f"  ⚠️  文件过小(可能抓取异常): {len(empty_or_bad)}")

    if missing:
        print(f"\n  缺失物种列表（前20个）:")
        for i, sp in enumerate(missing[:20], 1):
            print(f"    {i:3d}. {sp}")
        if len(missing) > 20:
            print(f"    ... 还有 {len(missing)-20} 个")

    if empty_or_bad:
        print(f"\n  文件过小的物种（前10个）:")
        for i, (sp, size) in enumerate(empty_or_bad[:10], 1):
            print(f"    {i:3d}. {sp} ({size} bytes)")

    # 5. 生成缺失名单 CSV
    if generate_missing and missing:
        with open(missing_csv, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(["species"])
            for sp in missing:
                writer.writerow([sp])
        print(f"\n📝 已生成缺失名单: {missing_csv} ({len(missing)} 条)")
        print(f"\n👉 下一步:")
        if source == "fna":
            print(f"   1. 修改 fna.py 中 input_csv_file = '{missing_csv}'")
            print(f"   2. 确保 CDP 浏览器已通过 Cloudflare 验证")
            print(f"   3. 运行 python fna.py")
        else:
            print(f"   1. 修改 foc.py 中 input_csv_file = '{missing_csv}'")
            print(f"   2. 运行 python foc.py")
        print(f"   4. 抓完后再次运行本脚本检查，直到缺失为 0")
    elif generate_missing and not missing:
        print(f"\n🎉 全部抓取完成，无缺失！")

    return missing


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="检查抓取完整性，生成缺失物种名单")
    parser.add_argument("--source", choices=["fna", "foc"], default="fna",
                        help="检查哪个来源: fna (默认) 或 foc")
    parser.add_argument("--fix", action="store_true",
                        help="生成缺失物种名单 CSV，供重新抓取")
    args = parser.parse_args()

    check(args.source, generate_missing=args.fix)
