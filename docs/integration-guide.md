# you-get 集成指南

本文档介绍如何在 Python 服务中集成 you-get 进行媒体下载。

## 快速开始

### 基本用法

```python
import subprocess

# 最简单的使用方式
def download_media(url):
    result = subprocess.run(['you-get', url], capture_output=True)
    return result.returncode == 0
```

### 判断下载是否成功

you-get 使用标准的 Unix 返回码：
- `0`: 成功
- `非0`: 失败

```python
import subprocess

result = subprocess.run(['you-get', url], capture_output=True, text=True)

if result.returncode == 0:
    print("下载成功")
    # 处理成功逻辑
else:
    print(f"下载失败，错误码: {result.returncode}")
    print(f"错误信息: {result.stderr}")
    # 处理失败逻辑
```

## 高级集成

### 1. 获取下载的文件

```python
import os
import subprocess

def download_and_get_file(url, output_dir="."):
    # 记录下载前的文件
    before_files = set(os.listdir(output_dir))
    
    # 执行下载
    cmd = ['you-get', '-o', output_dir, url]
    result = subprocess.run(cmd, capture_output=True)
    
    if result.returncode == 0:
        # 找到新下载的文件
        after_files = set(os.listdir(output_dir))
        new_files = list(after_files - before_files)
        
        if new_files:
            return {
                'success': True,
                'file': new_files[0],
                'path': os.path.join(output_dir, new_files[0])
            }
    
    return {'success': False, 'error': result.stderr}
```

### 2. 获取媒体信息

```python
import json
import subprocess

def get_media_info(url):
    cmd = ['you-get', '--json', url]
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode == 0:
        try:
            info = json.loads(result.stdout)
            return {
                'success': True,
                'title': info.get('title'),
                'url': info.get('url'),
                'streams': info.get('streams', {})
            }
        except json.JSONDecodeError:
            pass
    
    return {'success': False}
```

### 3. 带超时控制

```python
import subprocess

def download_with_timeout(url, timeout=300):
    try:
        result = subprocess.run(
            ['you-get', url],
            capture_output=True,
            timeout=timeout  # 5分钟超时
        )
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        print(f"下载超时（{timeout}秒）")
        return False
```

### 4. 异步下载

```python
import asyncio

async def async_download(url):
    proc = await asyncio.create_subprocess_exec(
        'you-get', url,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    
    stdout, stderr = await proc.communicate()
    
    return {
        'success': proc.returncode == 0,
        'stdout': stdout.decode(),
        'stderr': stderr.decode()
    }

# 使用示例
async def main():
    urls = ['url1', 'url2', 'url3']
    tasks = [async_download(url) for url in urls]
    results = await asyncio.gather(*tasks)
    
    for i, result in enumerate(results):
        print(f"URL {i+1}: {'成功' if result['success'] else '失败'}")
```

## 在 Web 框架中使用

### FastAPI 示例

```python
from fastapi import FastAPI, BackgroundTasks
import subprocess
import os

app = FastAPI()

def download_task(url: str, task_id: str):
    """后台下载任务"""
    output_dir = f"downloads/{task_id}"
    os.makedirs(output_dir, exist_ok=True)
    
    result = subprocess.run(
        ['you-get', '-o', output_dir, url],
        capture_output=True
    )
    
    # 更新数据库中的任务状态
    if result.returncode == 0:
        update_task_status(task_id, 'completed')
    else:
        update_task_status(task_id, 'failed', error=result.stderr)

@app.post("/download")
async def create_download(url: str, background_tasks: BackgroundTasks):
    task_id = generate_task_id()
    
    # 添加到后台任务
    background_tasks.add_task(download_task, url, task_id)
    
    return {"task_id": task_id, "status": "pending"}
```

### Django 示例

```python
# views.py
from django.http import JsonResponse
from django.views import View
import subprocess
import threading

class DownloadView(View):
    def post(self, request):
        url = request.POST.get('url')
        
        # 在新线程中执行下载
        thread = threading.Thread(
            target=self.download_media,
            args=(url, request.user.id)
        )
        thread.start()
        
        return JsonResponse({'status': 'started'})
    
    def download_media(self, url, user_id):
        result = subprocess.run(
            ['you-get', url],
            capture_output=True
        )
        
        # 保存结果到数据库
        DownloadRecord.objects.create(
            user_id=user_id,
            url=url,
            success=result.returncode == 0,
            error_msg=result.stderr if result.returncode != 0 else ''
        )
```

## 错误处理

### 常见错误码和处理方法

```python
def handle_download_error(return_code, stderr):
    """处理下载错误"""
    
    if return_code == 0:
        return {'success': True}
    
    # 分析错误信息
    error_msg = stderr.lower()
    
    if '403' in error_msg:
        return {
            'success': False,
            'error_type': 'forbidden',
            'message': '访问被拒绝（403）'
        }
    elif '404' in error_msg:
        return {
            'success': False,
            'error_type': 'not_found',
            'message': '资源不存在（404）'
        }
    elif 'timeout' in error_msg:
        return {
            'success': False,
            'error_type': 'timeout',
            'message': '下载超时'
        }
    elif '不支持' in stderr:
        return {
            'success': False,
            'error_type': 'unsupported',
            'message': '不支持的URL格式'
        }
    else:
        return {
            'success': False,
            'error_type': 'unknown',
            'message': f'未知错误（返回码: {return_code}）'
        }
```

## 性能优化

### 1. 使用进程池

```python
from concurrent.futures import ProcessPoolExecutor
import subprocess

def download_single(url):
    result = subprocess.run(['you-get', url], capture_output=True)
    return {
        'url': url,
        'success': result.returncode == 0
    }

def batch_download(urls, max_workers=4):
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        results = list(executor.map(download_single, urls))
    return results
```

### 2. 避免重复下载

```python
import os
import hashlib

def get_file_hash(url):
    """根据URL生成唯一标识"""
    return hashlib.md5(url.encode()).hexdigest()

def download_if_not_exists(url, output_dir):
    # 生成预期的文件名
    file_hash = get_file_hash(url)
    
    # 检查是否已存在
    existing_files = os.listdir(output_dir)
    for file in existing_files:
        if file_hash in file:
            return {
                'success': True,
                'skipped': True,
                'file': file
            }
    
    # 执行下载
    result = subprocess.run(
        ['you-get', '-o', output_dir, url],
        capture_output=True
    )
    
    return {
        'success': result.returncode == 0,
        'skipped': False
    }
```

## 监控和日志

```python
import logging
import time
import subprocess

logger = logging.getLogger(__name__)

def download_with_logging(url):
    """带日志记录的下载"""
    start_time = time.time()
    
    logger.info(f"开始下载: {url}")
    
    try:
        result = subprocess.run(
            ['you-get', url],
            capture_output=True,
            text=True,
            timeout=600
        )
        
        duration = time.time() - start_time
        
        if result.returncode == 0:
            logger.info(f"下载成功: {url} (耗时: {duration:.1f}秒)")
            # 记录到监控系统
            record_metric('download.success', 1)
            record_metric('download.duration', duration)
        else:
            logger.error(f"下载失败: {url} (错误: {result.stderr})")
            record_metric('download.failure', 1)
            
        return result.returncode == 0
        
    except subprocess.TimeoutExpired:
        logger.error(f"下载超时: {url}")
        record_metric('download.timeout', 1)
        return False
    except Exception as e:
        logger.exception(f"下载异常: {url}")
        record_metric('download.error', 1)
        return False
```

## 完整示例

完整的服务集成示例请参考 [you_get_service_example.py](./examples/you_get_service_example.py)

## 最佳实践

1. **设置合理的超时时间**：视频文件可能很大，建议设置 5-10 分钟的超时
2. **使用后台任务**：避免阻塞 Web 请求
3. **记录详细日志**：方便问题排查
4. **实现重试机制**：网络问题可能导致临时失败
5. **限制并发数**：避免过多并发下载占用带宽
6. **定期清理**：下载的文件可能占用大量磁盘空间