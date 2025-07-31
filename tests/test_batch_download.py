#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
测试 you-get 批量下载小红书图片功能
"""

import subprocess
import sys

# 测试URL列表（逗号分隔）
test_urls = 'http://sns-webpic-qc.xhscdn.com/202507311712/7a052ae0ccae8c550d74b43959b0d5da/1040g2sg319j56bevng005n33ecdk7ktpaqr9uc8!nd_dft_wgth_jpg_3,http://sns-webpic-qc.xhscdn.com/202507311712/942ff91b1216c3db5832a002f0beb178/1040g2sg319j56bevng0g5n33ecdk7ktpnv2ntco!nd_dft_wgth_jpg_3'

# 使用单引号避免 zsh 解析问题
print("测试批量下载小红书图片...")
print(f"URL数量: 2")
print("-" * 50)

# 执行 you-get 命令
cmd = ['python', '-m', 'you_get', test_urls]
print(f"执行命令: {' '.join(cmd)}")
print("-" * 50)

try:
    result = subprocess.run(cmd, capture_output=True, text=True)
    print("输出:")
    print(result.stdout)
    if result.stderr:
        print("错误:")
        print(result.stderr)
    print(f"返回码: {result.returncode}")
except Exception as e:
    print(f"执行失败: {e}")

print("\n提示:")
print("1. 如果在 zsh 中直接运行，请使用单引号包围URL:")
print("   you-get 'url1,url2,url3'")
print("2. 或者转义感叹号:")
print("   you-get url1\\!xxx,url2\\!xxx")
print("3. 也可以使用空格分隔多个URL（每个都用引号）:")
print("   you-get 'url1' 'url2' 'url3'")