#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
在服务中集成 you-get 的示例代码
"""

import subprocess
import os
import re
import json
import time
from pathlib import Path

class YouGetDownloader:
    """
    you-get 下载器封装类
    """
    
    def __init__(self, output_dir="./downloads", timeout=300):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.timeout = timeout
    
    def get_info(self, url):
        """
        获取媒体信息
        
        Returns:
            dict or None: 媒体信息
        """
        cmd = ['you-get', '--json', url]
        
        try:
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                return json.loads(result.stdout)
            return None
            
        except (subprocess.TimeoutExpired, json.JSONDecodeError):
            return None
    
    def download(self, url, custom_filename=None):
        """
        下载媒体文件
        
        Args:
            url: 媒体URL
            custom_filename: 自定义文件名（可选）
            
        Returns:
            dict: {
                'success': bool,
                'return_code': int,
                'file_path': str or None,
                'file_size': int or None,
                'error_msg': str or None,
                'duration': float  # 下载耗时（秒）
            }
        """
        start_time = time.time()
        
        # 构建命令
        cmd = ['you-get', '-o', str(self.output_dir)]
        
        # 如果指定了文件名
        if custom_filename:
            cmd.extend(['-O', custom_filename])
        
        cmd.append(url)
        
        # 记录下载前的文件
        before_files = set(self.output_dir.iterdir())
        
        try:
            # 执行下载
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout
            )
            
            # 计算耗时
            duration = time.time() - start_time
            
            # 检查是否成功
            if result.returncode == 0:
                # 找到新下载的文件
                after_files = set(self.output_dir.iterdir())
                new_files = after_files - before_files
                
                if new_files:
                    # 通常只有一个新文件
                    file_path = list(new_files)[0]
                    file_size = file_path.stat().st_size
                    
                    return {
                        'success': True,
                        'return_code': 0,
                        'file_path': str(file_path),
                        'file_size': file_size,
                        'error_msg': None,
                        'duration': duration
                    }
                else:
                    # 可能文件已存在（you-get 会跳过）
                    # 尝试从输出中解析文件名
                    file_name = self._parse_filename_from_output(result.stdout)
                    if file_name:
                        file_path = self.output_dir / file_name
                        if file_path.exists():
                            return {
                                'success': True,
                                'return_code': 0,
                                'file_path': str(file_path),
                                'file_size': file_path.stat().st_size,
                                'error_msg': 'File already exists',
                                'duration': duration
                            }
            
            # 下载失败
            error_msg = self._extract_error_message(result.stderr)
            return {
                'success': False,
                'return_code': result.returncode,
                'file_path': None,
                'file_size': None,
                'error_msg': error_msg,
                'duration': duration
            }
            
        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'return_code': -1,
                'file_path': None,
                'file_size': None,
                'error_msg': f'Download timeout after {self.timeout} seconds',
                'duration': self.timeout
            }
        except Exception as e:
            return {
                'success': False,
                'return_code': -2,
                'file_path': None,
                'file_size': None,
                'error_msg': str(e),
                'duration': time.time() - start_time
            }
    
    def batch_download(self, urls):
        """
        批量下载
        
        Args:
            urls: URL列表
            
        Returns:
            list: 每个URL的下载结果
        """
        results = []
        for i, url in enumerate(urls):
            print(f"下载进度: {i+1}/{len(urls)}")
            result = self.download(url)
            results.append({
                'url': url,
                'result': result
            })
        return results
    
    def _parse_filename_from_output(self, output):
        """从输出中解析文件名"""
        # 尝试匹配 "Downloading xxx.mp4 ..." 或 "Skipping xxx.mp4 ..."
        match = re.search(r'(?:Downloading|Skipping)\s+(.+?)\s+\.\.\.', output)
        if match:
            return match.group(1)
        return None
    
    def _extract_error_message(self, stderr):
        """提取错误信息"""
        if not stderr:
            return "Unknown error"
        
        # 提取关键错误信息
        if "403" in stderr:
            return "HTTP 403 Forbidden - Access denied"
        elif "404" in stderr:
            return "HTTP 404 Not Found - Resource not found"
        elif "不支持的" in stderr:
            return "Unsupported URL format"
        elif "timeout" in stderr.lower():
            return "Network timeout"
        else:
            # 返回最后一行非空错误信息
            lines = [line.strip() for line in stderr.split('\n') if line.strip()]
            return lines[-1] if lines else "Unknown error"


# 使用示例
if __name__ == "__main__":
    # 创建下载器实例
    downloader = YouGetDownloader(output_dir="./xhs_downloads")
    
    # 测试1: 下载小红书图片
    print("=== 测试下载小红书图片 ===")
    img_url = 'https://sns-webpic-qc.xhscdn.com/202507311712/7a052ae0ccae8c550d74b43959b0d5da/1040g2sg319j56bevng005n33ecdk7ktpaqr9uc8!nd_dft_wgth_jpg_3'
    result = downloader.download(img_url)
    
    if result['success']:
        print(f"✓ 下载成功!")
        print(f"  文件路径: {result['file_path']}")
        print(f"  文件大小: {result['file_size'] / 1024:.1f} KB")
        print(f"  耗时: {result['duration']:.1f} 秒")
    else:
        print(f"✗ 下载失败!")
        print(f"  错误码: {result['return_code']}")
        print(f"  错误信息: {result['error_msg']}")
    
    print("\n" + "="*50 + "\n")
    
    # 测试2: 批量下载
    print("=== 测试批量下载 ===")
    urls = [
        'https://sns-webpic-qc.xhscdn.com/202507311712/7a052ae0ccae8c550d74b43959b0d5da/1040g2sg319j56bevng005n33ecdk7ktpaqr9uc8!nd_dft_wgth_jpg_3',
        'https://sns-webpic-qc.xhscdn.com/202507311712/942ff91b1216c3db5832a002f0beb178/1040g2sg319j56bevng0g5n33ecdk7ktpnv2ntco!nd_dft_wgth_jpg_3'
    ]
    
    batch_results = downloader.batch_download(urls)
    
    # 统计结果
    success_count = sum(1 for r in batch_results if r['result']['success'])
    print(f"\n批量下载完成: {success_count}/{len(urls)} 成功")
    
    print("\n" + "="*50 + "\n")
    
    # 在实际服务中的使用示例
    print("=== 在服务中集成示例 ===")
    print("""
# 在 FastAPI 中使用
from fastapi import FastAPI, BackgroundTasks
from you_get_service import YouGetDownloader

app = FastAPI()
downloader = YouGetDownloader()

@app.post("/download")
async def download_media(url: str, background_tasks: BackgroundTasks):
    # 异步下载
    background_tasks.add_task(downloader.download, url)
    return {"message": "Download started"}

@app.post("/download-sync")
def download_media_sync(url: str):
    # 同步下载
    result = downloader.download(url)
    return result

# 在数据库任务中使用
def process_download_task(task_id, url):
    downloader = YouGetDownloader()
    
    # 更新任务状态为运行中
    update_task_status(task_id, 'running')
    
    # 执行下载
    result = downloader.download(url)
    
    if result['success']:
        # 更新任务状态为完成
        update_task_status(task_id, 'completed', 
                         file_path=result['file_path'],
                         file_size=result['file_size'])
    else:
        # 更新任务状态为失败
        update_task_status(task_id, 'failed',
                         error_msg=result['error_msg'])
    
    return result
    """)