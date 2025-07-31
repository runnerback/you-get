#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
测试 you-get 下载小红书视频功能
"""

import subprocess
import sys

# 测试视频URL
video_url = 'http://sns-video-bd.xhscdn.com/1040g00g31hp86o2ujil05n0qvba1br4f8mog4m0'

print("测试下载小红书视频...")
print(f"视频URL: {video_url}")
print("-" * 50)

# 执行 you-get 命令（使用 --debug 查看详细信息）
cmd = ['python', '-m', 'you_get', '--debug', video_url]
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

print("\n注意:")
print("1. 小红书视频可能需要特定的请求头")
print("2. 某些视频可能有时间限制或需要登录")
print("3. 如果遇到403错误，可能是代理问题（代码已自动禁用代理）")