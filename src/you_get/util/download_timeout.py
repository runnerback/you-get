#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
下载超时管理器
提供下载超时检测、重试机制和进度监控功能
"""

import json
import os
import time
import threading
import logging
from typing import Dict, Any, Optional, Callable
from urllib.error import HTTPError, URLError
import socket

logger = logging.getLogger(__name__)

class DownloadTimeoutError(Exception):
    """下载超时异常"""
    pass

class DownloadStallError(Exception):
    """下载停滞异常"""
    pass

class DownloadTimeoutManager:
    """下载超时管理器"""
    
    def __init__(self, config_path: str = None):
        self.config = self._load_config(config_path)
        self.download_start_time = None
        self.last_progress_time = None
        self.last_received_bytes = 0
        self.total_received_bytes = 0
        self.file_size = 0
        self.platform = "default"
        self.is_timeout_active = False
        self.timeout_thread = None
        self.download_timeout = 0
        self._lock = threading.Lock()
        
    def _load_config(self, config_path: str = None) -> Dict[str, Any]:
        """加载配置文件"""
        if config_path is None:
            # 获取当前文件的目录，然后找到config目录
            current_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
            config_path = os.path.join(project_root, "config", "download_timeout.json")
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                logger.debug(f"[超时管理] 加载配置文件成功: {config_path}")
                return config
        except Exception as e:
            logger.warning(f"[超时管理] 无法加载配置文件 {config_path}: {e}")
            return self._get_default_config()
    
    def _get_default_config(self) -> Dict[str, Any]:
        """获取默认配置"""
        return {
            "timeout_settings": {
                "socket_timeout": 600,
                "download_timeout": {
                    "small_file": {"max_size_mb": 50, "timeout_seconds": 300},
                    "medium_file": {"max_size_mb": 500, "timeout_seconds": 900},
                    "large_file": {"max_size_mb": 2048, "timeout_seconds": 1800},
                    "extra_large_file": {"max_size_mb": -1, "timeout_seconds": 3600}
                },
                "chunk_timeout": {"timeout_seconds": 30, "no_data_timeout": 60}
            },
            "retry_settings": {
                "max_retries": 3,
                "retry_delay": {"initial_delay": 2, "max_delay": 30, "backoff_factor": 2}
            },
            "progress_settings": {
                "stall_detection": {"max_stall_time": 60}
            },
            "platform_specific": {
                "default": {"timeout_multiplier": 1.0, "max_retries": 3}
            }
        }
    
    def _calculate_download_timeout(self, file_size: int) -> int:
        """根据文件大小计算下载超时时间"""
        size_mb = file_size / (1024 * 1024)
        timeout_config = self.config["timeout_settings"]["download_timeout"]
        
        if size_mb <= timeout_config["small_file"]["max_size_mb"]:
            base_timeout = timeout_config["small_file"]["timeout_seconds"]
        elif size_mb <= timeout_config["medium_file"]["max_size_mb"]:
            base_timeout = timeout_config["medium_file"]["timeout_seconds"]
        elif size_mb <= timeout_config["large_file"]["max_size_mb"]:
            base_timeout = timeout_config["large_file"]["timeout_seconds"]
        else:
            base_timeout = timeout_config["extra_large_file"]["timeout_seconds"]
        
        # 应用平台特定的倍数
        platform_config = self.config["platform_specific"].get(self.platform, 
                                                               self.config["platform_specific"]["default"])
        multiplier = platform_config.get("timeout_multiplier", 1.0)
        
        final_timeout = int(base_timeout * multiplier)
        logger.info(f"[超时管理] 文件大小: {size_mb:.1f}MB, 计算超时时间: {final_timeout}秒")
        return final_timeout
    
    def start_download(self, file_size: int, platform: str = "default"):
        """开始下载，启动超时监控"""
        with self._lock:
            self.file_size = file_size
            self.platform = platform
            self.download_start_time = time.time()
            self.last_progress_time = time.time()
            self.last_received_bytes = 0
            self.total_received_bytes = 0
            self.download_timeout = self._calculate_download_timeout(file_size)
            self.is_timeout_active = True
            
        # 启动超时监控线程
        if self.timeout_thread and self.timeout_thread.is_alive():
            self.is_timeout_active = False
            self.timeout_thread.join()
            
        self.timeout_thread = threading.Thread(target=self._timeout_monitor, daemon=True)
        self.timeout_thread.start()
        
        logger.info(f"[超时管理] 开始下载监控 - 平台: {platform}, 超时时间: {self.download_timeout}秒")
    
    def update_progress(self, received_bytes: int):
        """更新下载进度"""
        with self._lock:
            if not self.is_timeout_active:
                return
                
            current_time = time.time()
            self.total_received_bytes = received_bytes
            
            # 检查是否有新数据
            if received_bytes > self.last_received_bytes:
                self.last_progress_time = current_time
                self.last_received_bytes = received_bytes
    
    def stop_download(self):
        """停止下载监控"""
        with self._lock:
            self.is_timeout_active = False
            
        if self.timeout_thread and self.timeout_thread.is_alive():
            self.timeout_thread.join()
            
        logger.debug("[超时管理] 停止下载监控")
    
    def _timeout_monitor(self):
        """超时监控线程"""
        while self.is_timeout_active:
            try:
                current_time = time.time()
                
                with self._lock:
                    if not self.is_timeout_active:
                        break
                        
                    # 检查总体下载超时
                    elapsed_time = current_time - self.download_start_time
                    if elapsed_time > self.download_timeout:
                        logger.error(f"[超时管理] 下载总体超时: {elapsed_time:.1f}秒 > {self.download_timeout}秒")
                        self.is_timeout_active = False
                        raise DownloadTimeoutError(f"下载超时: {elapsed_time:.1f}秒")
                    
                    # 检查下载停滞
                    stall_time = current_time - self.last_progress_time
                    max_stall_time = self.config["progress_settings"]["stall_detection"]["max_stall_time"]
                    
                    if stall_time > max_stall_time:
                        logger.error(f"[超时管理] 下载停滞: {stall_time:.1f}秒无进度更新")
                        self.is_timeout_active = False
                        raise DownloadStallError(f"下载停滞: {stall_time:.1f}秒无进度")
                
                time.sleep(5)  # 每5秒检查一次
                
            except (DownloadTimeoutError, DownloadStallError):
                raise
            except Exception as e:
                logger.error(f"[超时管理] 监控线程异常: {e}")
                break
    
    def get_max_retries(self) -> int:
        """获取最大重试次数"""
        platform_config = self.config["platform_specific"].get(self.platform,
                                                               self.config["platform_specific"]["default"])
        return platform_config.get("max_retries", self.config["retry_settings"]["max_retries"])
    
    def get_retry_delay(self, attempt: int) -> float:
        """获取重试延迟时间"""
        retry_config = self.config["retry_settings"]["retry_delay"]
        initial_delay = retry_config["initial_delay"]
        max_delay = retry_config["max_delay"]
        backoff_factor = retry_config["backoff_factor"]
        
        delay = initial_delay * (backoff_factor ** (attempt - 1))
        return min(delay, max_delay)
    
    def should_retry(self, exception: Exception) -> bool:
        """判断是否应该重试"""
        retry_conditions = self.config["retry_settings"]["retry_conditions"]
        
        # 检查超时异常
        if isinstance(exception, (DownloadTimeoutError, DownloadStallError, socket.timeout)):
            return retry_conditions.get("timeout", True)
        
        # 检查连接错误
        if isinstance(exception, (URLError, ConnectionError)):
            return retry_conditions.get("connection_error", True)
        
        # 检查HTTP错误码
        if isinstance(exception, HTTPError):
            error_codes = retry_conditions.get("http_error_codes", [])
            return exception.code in error_codes
        
        return False

class DownloadRetryManager:
    """下载重试管理器"""
    
    def __init__(self, timeout_manager: DownloadTimeoutManager):
        self.timeout_manager = timeout_manager
        
    def download_with_retry(self, download_func: Callable, *args, **kwargs) -> Any:
        """带重试的下载执行器"""
        max_retries = self.timeout_manager.get_max_retries()
        last_exception = None
        
        for attempt in range(max_retries + 1):
            try:
                if attempt > 0:
                    delay = self.timeout_manager.get_retry_delay(attempt)
                    logger.info(f"[重试管理] 第{attempt}次重试，延迟{delay:.1f}秒...")
                    time.sleep(delay)
                
                # 执行下载
                logger.info(f"[重试管理] 开始下载尝试 {attempt + 1}/{max_retries + 1}")
                return download_func(*args, **kwargs)
                
            except Exception as e:
                last_exception = e
                logger.warning(f"[重试管理] 第{attempt + 1}次尝试失败: {e}")
                
                # 检查是否应该重试
                if attempt < max_retries and self.timeout_manager.should_retry(e):
                    logger.info(f"[重试管理] 准备重试...")
                    continue
                else:
                    if attempt >= max_retries:
                        logger.error(f"[重试管理] 达到最大重试次数({max_retries})，放弃下载")
                    else:
                        logger.error(f"[重试管理] 异常不符合重试条件，放弃下载")
                    break
        
        # 所有重试都失败了
        raise last_exception or Exception("下载失败且无具体异常信息")

# 全局超时管理器实例
_timeout_manager_instance = None

def get_timeout_manager() -> DownloadTimeoutManager:
    """获取全局超时管理器实例"""
    global _timeout_manager_instance
    if _timeout_manager_instance is None:
        _timeout_manager_instance = DownloadTimeoutManager()
    return _timeout_manager_instance

def get_retry_manager() -> DownloadRetryManager:
    """获取重试管理器实例"""
    timeout_manager = get_timeout_manager()
    return DownloadRetryManager(timeout_manager)

if __name__ == "__main__":
    # 测试代码
    logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
    
    # 测试超时管理器
    manager = DownloadTimeoutManager()
    
    # 模拟小文件下载
    print("测试小文件下载超时计算...")
    manager.start_download(30 * 1024 * 1024, "bilibili")  # 30MB
    
    # 模拟进度更新
    for i in range(10):
        manager.update_progress(i * 3 * 1024 * 1024)
        time.sleep(0.1)
    
    manager.stop_download()
    print("测试完成！") 