#!/usr/bin/env python

from ..common import *
from ..extractor import VideoExtractor
import re

class Xiaohongshu(VideoExtractor):
    name = "小红书 (Xiaohongshu)"
    
    stream_types = [
        {'id': 'original'},
    ]
    
    def prepare(self, **kwargs):
        # 声明 global 变量
        global fake_headers
        
        # 小红书不能使用代理，需要临时禁用
        import os
        original_http_proxy = os.environ.get('http_proxy')
        original_https_proxy = os.environ.get('https_proxy')
        
        # 临时禁用代理
        if 'http_proxy' in os.environ:
            del os.environ['http_proxy']
        if 'https_proxy' in os.environ:
            del os.environ['https_proxy']
        
        # 处理小红书CDN图片和视频直链
        if re.search(r'(sns-webpic-qc|sns-img-qc|sns-img-hw|sns-img-bd|sns-img-qn|sns-video-bd|sns-video-qc|sns-video-hw|sns-video-qn)\.xhscdn\.com', self.url):
            # 确保使用 https 协议
            if self.url.startswith('http://'):
                self.url = self.url.replace('http://', 'https://', 1)
            
            # 判断是视频还是图片
            is_video = 'sns-video' in self.url
            
            if is_video:
                # 视频默认格式为 mp4
                container = 'mp4'
                # 设置视频请求头
                fake_headers['Accept'] = 'video/webm,video/ogg,video/*;q=0.9,application/ogg;q=0.7,audio/*;q=0.6,*/*;q=0.5'
            else:
                # 从URL中提取文件扩展名
                # 处理类似 !nd_dft_wlteh_jpg_3 这样的后缀
                container = 'jpg'  # 默认格式
                if '!nd_dft_wlteh_jpg' in self.url:
                    container = 'jpg'
                elif '!nd_dft_wlteh_png' in self.url:
                    container = 'png'
                elif '!nd_dft_wlteh_webp' in self.url:
                    container = 'webp'
                elif '.jpg' in self.url:
                    container = 'jpg'
                elif '.png' in self.url:
                    container = 'png'
                elif '.webp' in self.url:
                    container = 'webp'
                # 设置图片请求头
                fake_headers['Accept'] = 'image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8'
            
            # 设置必要的请求头，模拟从小红书网站访问
            self.referer = 'https://www.xiaohongshu.com/'
            
            # 修改全局 fake_headers 以支持小红书
            fake_headers['Referer'] = self.referer
            fake_headers['Accept-Language'] = 'zh-CN,zh;q=0.9,en;q=0.8'
            fake_headers['Cache-Control'] = 'no-cache'
            fake_headers['Pragma'] = 'no-cache'
            
            # 获取图片大小
            try:
                _, _, size = url_info(self.url, faker=True)  # 使用 faker=True 让它使用 fake_headers
            except:
                size = 0
            
            # 设置下载流
            self.streams = {
                'original': {
                    'src': [self.url],
                    'size': size,
                    'container': container
                }
            }
            
            # 从URL中提取标题
            # 尝试从路径中获取有意义的名称
            if is_video:
                # 视频URL格式：.../1040g00g31hp86o2ujil05n0qvba1br4f8mog4m0
                match = re.search(r'/([a-zA-Z0-9]+)$', self.url)
                if match:
                    self.title = match.group(1)
                else:
                    self.title = 'xiaohongshu_video'
            else:
                # 图片URL格式：.../xxx!nd_dft_wlteh_jpg_3
                match = re.search(r'/([a-zA-Z0-9]+)(?:!|\.)', self.url)
                if match:
                    self.title = match.group(1)
                else:
                    self.title = 'xiaohongshu_image'
                
        # 处理小红书笔记页面URL
        elif re.search(r'xiaohongshu\.com/explore/|xiaohongshu\.com/discovery/item/', self.url):
            # 这里可以后续扩展，支持从笔记页面提取图片和视频
            raise NotImplementedError("小红书笔记页面解析暂未实现，请使用图片直链")
        
        else:
            raise Exception("不支持的小红书URL格式")
        
        # 恢复原始代理设置
        if original_http_proxy:
            os.environ['http_proxy'] = original_http_proxy
        if original_https_proxy:
            os.environ['https_proxy'] = original_https_proxy
    
    def extract(self, **kwargs):
        """覆盖提取方法"""
        if 'stream_id' in kwargs and kwargs['stream_id']:
            # 只处理指定的流
            stream_id = kwargs['stream_id']
            if stream_id in self.streams:
                s = self.streams[stream_id]
                if 'size' not in s or s['size'] == 0:
                    _, s['container'], s['size'] = url_info(s['src'][0], faker=True)
    
    def download(self, **kwargs):
        """重写下载方法以传递正确的请求头"""
        # 小红书下载时也需要禁用代理
        import os
        original_http_proxy = os.environ.get('http_proxy')
        original_https_proxy = os.environ.get('https_proxy')
        
        # 临时禁用代理
        if 'http_proxy' in os.environ:
            del os.environ['http_proxy']
        if 'https_proxy' in os.environ:
            del os.environ['https_proxy']
        
        try:
            # 确保 fake_headers 包含必要的头
            global fake_headers
            if hasattr(self, 'referer'):
                fake_headers['Referer'] = self.referer
            
            # 为每个流下载
            for stream_id in self.streams:
                stream = self.streams[stream_id]
                # 使用 faker=True 来确保使用我们的 fake_headers
                download_urls(
                    stream['src'], 
                    self.title, 
                    stream['container'], 
                    stream['size'],
                    faker=True,  # 这个很重要！
                    **kwargs
                )
        finally:
            # 恢复原始代理设置
            if original_http_proxy:
                os.environ['http_proxy'] = original_http_proxy
            if original_https_proxy:
                os.environ['https_proxy'] = original_https_proxy

# 注册站点
site = Xiaohongshu()
download = site.download_by_url
download_playlist = site.download_by_url