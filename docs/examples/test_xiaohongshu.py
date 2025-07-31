#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
测试 you-get 小红书功能
"""

import subprocess
import sys
import os

def test_xhs_image():
    """测试小红书图片下载"""
    print("=== 测试小红书图片下载 ===")
    
    # 测试图片URL
    image_url = 'https://sns-webpic-qc.xhscdn.com/202507311712/7a052ae0ccae8c550d74b43959b0d5da/1040g2sg319j56bevng005n33ecdk7ktpaqr9uc8!nd_dft_wgth_jpg_3'
    
    # 执行下载
    cmd = ['python', '-m', 'you_get', image_url]
    print(f"执行命令: {' '.join(cmd)}")
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode == 0:
        print("✓ 图片下载成功!")
    else:
        print("✗ 图片下载失败!")
        print(f"错误信息: {result.stderr}")
    
    return result.returncode == 0

def test_xhs_video():
    """测试小红书视频下载"""
    print("\n=== 测试小红书视频下载 ===")
    
    # 测试视频URL
    video_url = 'http://sns-video-bd.xhscdn.com/1040g00g31hp86o2ujil05n0qvba1br4f8mog4m0'
    
    # 执行下载
    cmd = ['python', '-m', 'you_get', video_url]
    print(f"执行命令: {' '.join(cmd)}")
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode == 0:
        print("✓ 视频下载成功!")
        # 查找下载的文件
        mp4_files = [f for f in os.listdir('.') if f.endswith('.mp4')]
        if mp4_files:
            print(f"  下载的文件: {mp4_files[-1]}")
    else:
        print("✗ 视频下载失败!")
        print(f"错误信息: {result.stderr}")
    
    return result.returncode == 0

def test_batch_download():
    """测试批量下载"""
    print("\n=== 测试批量下载（逗号分隔） ===")
    
    # 批量URL（逗号分隔）
    batch_urls = 'https://sns-webpic-qc.xhscdn.com/202507311712/7a052ae0ccae8c550d74b43959b0d5da/1040g2sg319j56bevng005n33ecdk7ktpaqr9uc8!nd_dft_wgth_jpg_3,https://sns-webpic-qc.xhscdn.com/202507311712/942ff91b1216c3db5832a002f0beb178/1040g2sg319j56bevng0g5n33ecdk7ktpnv2ntco!nd_dft_wgth_jpg_3'
    
    # 执行下载
    cmd = ['python', '-m', 'you_get', batch_urls]
    print(f"执行命令: python -m you_get '<2个逗号分隔的URL>'")
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode == 0:
        print("✓ 批量下载成功!")
    else:
        print("✗ 批量下载失败!")
        print(f"错误信息: {result.stderr}")
    
    return result.returncode == 0

def test_json_info():
    """测试获取JSON信息"""
    print("\n=== 测试获取媒体信息（JSON格式） ===")
    
    # 测试URL
    test_url = 'https://sns-webpic-qc.xhscdn.com/202507311712/7a052ae0ccae8c550d74b43959b0d5da/1040g2sg319j56bevng005n33ecdk7ktpaqr9uc8!nd_dft_wgth_jpg_3'
    
    # 获取JSON信息
    cmd = ['python', '-m', 'you_get', '--json', test_url]
    print(f"执行命令: {' '.join(cmd)}")
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode == 0:
        print("✓ 获取信息成功!")
        # 解析并显示部分信息
        try:
            import json
            info = json.loads(result.stdout)
            print(f"  标题: {info.get('title', 'N/A')}")
            print(f"  URL: {info.get('url', 'N/A')}")
            if 'streams' in info:
                for stream_id, stream_info in info['streams'].items():
                    print(f"  流 {stream_id}: {stream_info.get('container', 'N/A')} 格式")
        except:
            pass
    else:
        print("✗ 获取信息失败!")
        print(f"错误信息: {result.stderr}")
    
    return result.returncode == 0

if __name__ == "__main__":
    print("小红书 you-get 功能测试")
    print("=" * 50)
    
    # 运行所有测试
    results = {
        '图片下载': test_xhs_image(),
        '视频下载': test_xhs_video(),
        '批量下载': test_batch_download(),
        'JSON信息': test_json_info()
    }
    
    # 显示总结
    print("\n" + "=" * 50)
    print("测试结果总结:")
    for test_name, passed in results.items():
        status = "✓ 通过" if passed else "✗ 失败"
        print(f"  {test_name}: {status}")
    
    # 返回总体结果
    all_passed = all(results.values())
    sys.exit(0 if all_passed else 1)