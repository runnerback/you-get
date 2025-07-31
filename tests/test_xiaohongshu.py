#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
测试小红书图片下载功能
"""

import sys
import os

# 添加 you-get 源码路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from you_get.common import any_download

# 测试图片URL
test_urls = [
    # HTTP URL - 应该自动转换为 HTTPS
    "http://sns-webpic-qc.xhscdn.com/202507311712/c5c6a7373e27cfe7788bb10fc2cff5e6/1040g2sg31kaovsncj0gg5panliui5q83kfp0t6o!nd_dft_wlteh_jpg_3",
    
    # HTTPS URL
    "https://sns-webpic-qc.xhscdn.com/202507311712/c5c6a7373e27cfe7788bb10fc2cff5e6/1040g2sg31kaovsncj0gg5panliui5q83kfp0t6o!nd_dft_wlteh_jpg_3",
]

def test_download():
    """测试下载功能"""
    print("=== 小红书图片下载测试 ===\n")
    
    # 创建测试输出目录
    output_dir = "./test_output"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    for i, url in enumerate(test_urls, 1):
        print(f"\n--- 测试 {i}: ---")
        print(f"URL: {url}")
        
        try:
            # 使用 --info 参数只显示信息，不实际下载
            print("\n1. 获取信息（不下载）:")
            any_download(url, info_only=True)
            
            # 实际下载
            print(f"\n2. 下载到目录: {output_dir}")
            any_download(url, output_dir=output_dir)
            
            print(f"\n✅ 测试 {i} 成功!")
            
        except Exception as e:
            print(f"\n❌ 测试 {i} 失败: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n=== 测试完成 ===")

if __name__ == '__main__':
    test_download()