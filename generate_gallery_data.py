#!/usr/bin/env python3
"""
扫描 gallery 目录，为每个子文件夹生成图片列表
输出 JSON 文件供前端使用
"""

import os
import json
from pathlib import Path

def scan_gallery_images(gallery_root):
    """
    扫描 gallery 目录下所有子文件夹的图片
    返回格式: { "metric_name": ["image1.jpg", "image2.png", ...] }
    """
    gallery_path = Path(gallery_root)
    result = {}

    # 支持的图片格式
    image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'}

    # 遍历 gallery 下的每个子文件夹
    for folder in sorted(gallery_path.iterdir()):
        if not folder.is_dir():
            continue

        metric_name = folder.name
        images = []

        # 收集该文件夹下所有图片
        for file in sorted(folder.iterdir()):
            if file.is_file() and file.suffix.lower() in image_extensions:
                # 使用相对路径 gallery/metric_name/image.jpg
                relative_path = f"gallery/{metric_name}/{file.name}"
                images.append(relative_path)

        if images:
            result[metric_name] = images

    return result

def main():
    # gallery 目录路径（相对于脚本所在目录）
    script_dir = Path(__file__).parent
    gallery_dir = script_dir / "gallery"

    if not gallery_dir.exists():
        print(f"错误: gallery 目录不存在: {gallery_dir}")
        return

    print(f"扫描目录: {gallery_dir}")

    # 扫描图片
    gallery_data = scan_gallery_images(gallery_dir)

    # 输出 JSON 文件
    output_file = script_dir / "gallery_data.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(gallery_data, f, indent=2, ensure_ascii=False)

    print(f"\n生成完成: {output_file}")
    print(f"找到 {len(gallery_data)} 个 metrics:")
    for metric, images in gallery_data.items():
        print(f"  - {metric}: {len(images)} 张图片")

if __name__ == "__main__":
    main()
