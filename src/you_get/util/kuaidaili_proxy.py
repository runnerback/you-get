#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
快代理IP代理实现
基于快代理API文档：https://www.kuaidaili.cn/doc/dev/dps/
支持跨进程的IP缓存共享，避免重复消耗IP
"""

import re
import json
import time
import logging
import os
import tempfile
import fcntl
from typing import Dict, List, Optional
from urllib import request, parse, error

logger = logging.getLogger(__name__)

class KuaidailiProxyModel:
    """快代理IP信息模型"""
    
    def __init__(self, ip: str, port: int, expire_ts: int):
        self.ip = ip
        self.port = port
        self.expire_ts = expire_ts
        
    def __str__(self):
        return f"{self.ip}:{self.port}"
    
    def to_dict(self):
        """转换为字典格式用于JSON序列化"""
        return {
            'ip': self.ip,
            'port': self.port,
            'expire_ts': self.expire_ts
        }
    
    @classmethod
    def from_dict(cls, data):
        """从字典创建实例"""
        return cls(data['ip'], data['port'], data['expire_ts'])

class KuaidailiProxy:
    """快代理实现类（支持跨进程缓存）"""
    
    def __init__(self, secret_id: str, signature: str, username: str = None, password: str = None):
        self.secret_id = secret_id
        self.signature = signature
        self.username = username or ""
        self.password = password or ""
        self.api_base = "https://dps.kdlapi.com"
        self.cache = {}  # 内存缓存
        self.cache_file = os.path.join(tempfile.gettempdir(), "kuaidaili_proxy_cache.json")
        
    def _load_cache_from_file(self):
        """从文件加载缓存（跨进程共享）"""
        try:
            if not os.path.exists(self.cache_file):
                return {}
                
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                # 使用文件锁防止并发读写冲突
                fcntl.flock(f.fileno(), fcntl.LOCK_SH)
                data = json.load(f)
                
                # 清理过期的缓存
                current_time = time.time()
                valid_cache = {}
                for key, cache_data in data.items():
                    if cache_data.get('expire_time', 0) > current_time:
                        valid_cache[key] = cache_data
                        
                logger.debug(f"[快代理缓存] 从文件加载了{len(valid_cache)}个有效IP")
                return valid_cache
                
        except Exception as e:
            logger.warning(f"[快代理缓存] 加载缓存文件失败: {e}")
            return {}
    
    def _save_cache_to_file(self, cache_data):
        """保存缓存到文件（跨进程共享）"""
        try:
            # 创建临时文件，原子性写入
            temp_file = self.cache_file + ".tmp"
            with open(temp_file, 'w', encoding='utf-8') as f:
                # 使用文件锁防止并发读写冲突
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
                
            # 原子性重命名
            os.rename(temp_file, self.cache_file)
            logger.debug(f"[快代理缓存] 保存缓存到文件: {len(cache_data)}个IP")
            
        except Exception as e:
            logger.warning(f"[快代理缓存] 保存缓存文件失败: {e}")
        
    def parse_proxy_info(self, proxy_info: str) -> KuaidailiProxyModel:
        """
        解析快代理返回的IP信息
        格式: ip:port,expire_seconds
        """
        pattern = r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}):(\d{1,5}),(\d+)'
        match = re.search(pattern, proxy_info)
        if not match:
            raise Exception(f"Invalid kuaidaili proxy format: {proxy_info}")
            
        ip = match.group(1)
        port = int(match.group(2))
        expire_ts = int(match.group(3))
        
        return KuaidailiProxyModel(ip, port, expire_ts)
        
    def get_proxy_from_api(self, num: int = 1) -> List[KuaidailiProxyModel]:
        """
        从快代理API获取代理IP
        """
        url = f"{self.api_base}/api/getdps"
        params = {
            "secret_id": self.secret_id,
            "signature": self.signature,
            "num": num,
            "pt": 1,  # 协议类型：1-HTTP，2-HTTPS，3-SOCKS5
            "format": "json",
            "sep": 1,  # 分隔符：1-回车换行，2-json
            "f_et": 1,  # 返回剩余时间
        }
        
        url_with_params = f"{url}?{parse.urlencode(params)}"
        
        try:
            req = request.Request(url_with_params)
            with request.urlopen(req, timeout=10) as response:
                if response.status != 200:
                    raise Exception(f"API request failed with status {response.status}")
                    
                data = json.loads(response.read().decode('utf-8'))
                
                if data.get('code') != 0:
                    raise Exception(f"API returned error: {data.get('msg', 'Unknown error')}")
                    
                proxy_list = data.get('data', {}).get('proxy_list', [])
                if not proxy_list:
                    raise Exception("No proxy returned from API")
                    
                proxies = []
                for proxy_str in proxy_list:
                    try:
                        proxy = self.parse_proxy_info(proxy_str)
                        proxies.append(proxy)
                    except Exception as e:
                        logger.warning(f"Failed to parse proxy {proxy_str}: {e}")
                        
                return proxies
                
        except Exception as e:
            logger.error(f"Failed to get proxy from kuaidaili API: {e}")
            raise
            
    def get_valid_proxy(self) -> Optional[KuaidailiProxyModel]:
        """
        获取一个有效的代理IP
        优先从缓存获取（包括跨进程缓存），如果没有则从API获取
        """
        current_time = time.time()
        
        # 1. 先检查内存缓存
        expired_keys = [k for k, v in self.cache.items() 
                       if v['expire_time'] <= current_time]
        for key in expired_keys:
            del self.cache[key]
            
        for cache_data in self.cache.values():
            if cache_data['expire_time'] > current_time:
                proxy_dict = cache_data['proxy']
                proxy = KuaidailiProxyModel.from_dict(proxy_dict)
                logger.info(f"[快代理缓存] 使用内存缓存的IP: {proxy}")
                return proxy
        
        # 2. 检查文件缓存（跨进程共享）
        file_cache = self._load_cache_from_file()
        for cache_key, cache_data in file_cache.items():
            if cache_data.get('expire_time', 0) > current_time:
                proxy_dict = cache_data['proxy']
                proxy = KuaidailiProxyModel.from_dict(proxy_dict)
                
                # 将文件缓存的数据加载到内存缓存
                self.cache[cache_key] = cache_data
                
                logger.info(f"[快代理缓存] 使用文件缓存的IP: {proxy} (剩余{int(cache_data['expire_time'] - current_time)}秒)")
                return proxy
                
        # 3. 缓存中没有有效的，从API获取新IP
        try:
            logger.info("[快代理API] 缓存中无有效IP，从API获取新IP...")
            proxies = self.get_proxy_from_api(num=1)
            if proxies:
                proxy = proxies[0]
                
                # 存入内存缓存和文件缓存（提前5秒过期以确保安全）
                cache_key = f"{proxy.ip}:{proxy.port}"
                expire_time = current_time + proxy.expire_ts - 5
                cache_data = {
                    'proxy': proxy.to_dict(),
                    'expire_time': expire_time,
                    'created_time': current_time
                }
                
                # 更新内存缓存
                self.cache[cache_key] = cache_data
                
                # 更新文件缓存
                file_cache[cache_key] = cache_data
                self._save_cache_to_file(file_cache)
                
                logger.info(f"[快代理API] 获取新IP成功: {proxy} (有效期: {proxy.expire_ts}秒)")
                return proxy
            else:
                logger.error("[快代理API] API返回为空")
                return None
                
        except Exception as e:
            logger.error(f"[快代理API] 获取IP失败: {e}")
            return None
            
    def mark_proxy_invalid(self, proxy: KuaidailiProxyModel):
        """
        标记代理为无效，从内存和文件缓存中移除
        """
        cache_key = f"{proxy.ip}:{proxy.port}"
        
        # 从内存缓存移除
        if cache_key in self.cache:
            del self.cache[cache_key]
            
        # 从文件缓存移除
        try:
            file_cache = self._load_cache_from_file()
            if cache_key in file_cache:
                del file_cache[cache_key]
                self._save_cache_to_file(file_cache)
                
            logger.warning(f"[快代理缓存] 标记IP为无效并移除: {proxy}")
        except Exception as e:
            logger.error(f"[快代理缓存] 移除无效IP失败: {e}")

def create_kuaidaili_proxy() -> Optional[KuaidailiProxy]:
    """
    创建快代理实例
    从环境变量或配置文件读取配置
    """
    # 优先从环境变量读取
    secret_id = os.getenv("KDL_SECERT_ID")
    signature = os.getenv("KDL_SIGNATURE") 
    username = os.getenv("KDL_USER_NAME")
    password = os.getenv("KDL_USER_PWD")
    
    # 如果环境变量没有，尝试从配置文件读取
    if not secret_id or not signature:
        try:
            # 尝试读取 MediaCrawlerPro-Python 的配置
            config_path = "../../MediaCrawlerPro-Python/config/proxy_config.py"
            if os.path.exists(config_path):
                import sys
                sys.path.append(os.path.dirname(config_path))
                try:
                    from proxy_config import KDL_SECERT_ID, KDL_SIGNATURE, KDL_USER_NAME, KDL_USER_PWD
                    secret_id = secret_id or KDL_SECERT_ID
                    signature = signature or KDL_SIGNATURE
                    username = username or KDL_USER_NAME
                    password = password or KDL_USER_PWD
                except ImportError:
                    pass
        except Exception as e:
            logger.debug(f"Failed to import proxy config: {e}")
    
    # 使用文档中的默认值作为后备
    secret_id = secret_id or "ol7wcu6o50mq874weoi7"
    signature = signature or "tmg4u5957ro2l6hzs2d3nb1udou7relk"
    username = username or "d4348355574"
    password = password or "gxqsl7gd"
    
    if secret_id and signature:
        return KuaidailiProxy(secret_id, signature, username, password)
    else:
        logger.warning("快代理配置不完整，无法创建代理实例")
        return None

# 全局快代理实例
_kuaidaili_instance = None

def get_kuaidaili_proxy_instance() -> Optional[KuaidailiProxy]:
    """获取全局快代理实例"""
    global _kuaidaili_instance
    if _kuaidaili_instance is None:
        _kuaidaili_instance = create_kuaidaili_proxy()
    return _kuaidaili_instance

def get_kuaidaili_proxy_url() -> Optional[str]:
    """
    获取快代理的代理URL
    返回格式: http://username:password@ip:port
    """
    proxy_instance = get_kuaidaili_proxy_instance()
    if not proxy_instance:
        return None
        
    proxy = proxy_instance.get_valid_proxy()
    if not proxy:
        return None
        
    if proxy_instance.username and proxy_instance.password:
        return f"http://{proxy_instance.username}:{proxy_instance.password}@{proxy.ip}:{proxy.port}"
    else:
        return f"http://{proxy.ip}:{proxy.port}"

if __name__ == "__main__":
    # 测试代码
    logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
    
    print("测试跨进程IP缓存...")
    
    # 第一次获取
    print("第一次获取IP:")
    proxy_url = get_kuaidaili_proxy_url()
    if proxy_url:
        print(f"  获取到快代理URL: {proxy_url}")
    else:
        print("  获取快代理失败")
    
    print("\n第二次获取IP（应该使用缓存）:")
    proxy_url = get_kuaidaili_proxy_url()
    if proxy_url:
        print(f"  获取到快代理URL: {proxy_url}")
    else:
        print("  获取快代理失败") 