#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
测试 you-get 的返回值机制
"""

import subprocess
import os
import json

def test_download(url, output_dir="."):
    """
    测试下载并返回状态
    
    Returns:
        dict: {
            'success': bool,  # 是否成功
            'return_code': int,  # 返回码
            'stdout': str,  # 标准输出
            'stderr': str,  # 错误输出
            'downloaded_file': str or None  # 下载的文件名
        }
    """
    # 记录下载前的文件列表
    before_files = set(os.listdir(output_dir))
    
    # 执行 you-get 命令
    cmd = ['python', '-m', 'you_get', '-o', output_dir, url]
    
    try:
        result = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True,
            timeout=300  # 5分钟超时
        )
        
        # 记录下载后的文件列表
        after_files = set(os.listdir(output_dir))
        new_files = after_files - before_files
        
        # 判断是否成功
        success = result.returncode == 0
        
        # 找到新下载的文件
        downloaded_file = None
        if new_files:
            # 通常只有一个新文件
            downloaded_file = list(new_files)[0]
        
        return {
            'success': success,
            'return_code': result.returncode,
            'stdout': result.stdout,
            'stderr': result.stderr,
            'downloaded_file': downloaded_file
        }
        
    except subprocess.TimeoutExpired:
        return {
            'success': False,
            'return_code': -1,
            'stdout': '',
            'stderr': 'Download timeout after 300 seconds',
            'downloaded_file': None
        }
    except Exception as e:
        return {
            'success': False,
            'return_code': -2,
            'stdout': '',
            'stderr': str(e),
            'downloaded_file': None
        }

def test_download_with_info(url):
    """
    先获取视频信息，再下载
    """
    # 获取视频信息
    cmd_info = ['python', '-m', 'you_get', '--json', url]
    
    try:
        result = subprocess.run(cmd_info, capture_output=True, text=True)
        if result.returncode == 0:
            # 解析JSON信息
            info = json.loads(result.stdout)
            print("视频信息:", json.dumps(info, indent=2, ensure_ascii=False))
        else:
            print("获取信息失败")
    except:
        pass
    
    # 执行下载
    return test_download(url)

# 测试案例
print("=== 测试1: 正常的小红书图片 ===")
result1 = test_download('https://sns-webpic-qc.xhscdn.com/202507311712/7a052ae0ccae8c550d74b43959b0d5da/1040g2sg319j56bevng005n33ecdk7ktpaqr9uc8!nd_dft_wgth_jpg_3')
print(f"成功: {result1['success']}")
print(f"返回码: {result1['return_code']}")
print(f"下载文件: {result1['downloaded_file']}")
print()

print("=== 测试2: 错误的URL ===")
result2 = test_download('https://invalid-url-test.com/test.mp4')
print(f"成功: {result2['success']}")
print(f"返回码: {result2['return_code']}")
print(f"错误信息: {result2['stderr'][:200]}...")
print()

print("=== 在其他服务中使用示例 ===")
print("""
# 方法1: 使用 subprocess
import subprocess

def download_xhs_media(url, output_dir):
    cmd = ['you-get', '-o', output_dir, url]
    result = subprocess.run(cmd, capture_output=True)
    
    if result.returncode == 0:
        print("下载成功")
        return True
    else:
        print(f"下载失败，错误码: {result.returncode}")
        return False

# 方法2: 使用 os.system（简单但功能有限）
import os

def download_simple(url):
    exit_code = os.system(f"you-get '{url}'")
    return exit_code == 0

# 方法3: 检查文件是否存在
import os
import time

def download_and_verify(url, expected_filename):
    # 执行下载
    exit_code = os.system(f"you-get '{url}'")
    
    # 检查文件
    if exit_code == 0 and os.path.exists(expected_filename):
        file_size = os.path.getsize(expected_filename)
        if file_size > 0:
            return True
    return False
""")