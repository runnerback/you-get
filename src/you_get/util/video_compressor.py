#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import subprocess
import logging
from ..processor.ffmpeg import FFMPEG, has_ffmpeg_installed, LOGLEVEL, STDIN

log = logging.getLogger(__name__)

class VideoCompressor:
    """视频压缩工具类"""
    
    def __init__(self):
        if not has_ffmpeg_installed():
            raise Exception("FFmpeg 未安装或无法使用")
            
    def get_video_info(self, video_path):
        """获取视频信息"""
        try:
            params = [FFMPEG, '-i', video_path]
            result = subprocess.run(params, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            # FFmpeg 将信息输出到 stderr
            info = result.stderr
            
            # 解析视频分辨率
            import re
            resolution_match = re.search(r'Stream.*Video.* (\d+)x(\d+)', info)
            if resolution_match:
                width = int(resolution_match.group(1))
                height = int(resolution_match.group(2))
                return {'width': width, 'height': height}
            return None
        except Exception as e:
            log.error(f"获取视频信息失败: {e}")
            return None
    
    def calculate_scale(self, width, height, target_long_side=640):
        """计算缩放参数"""
        # 获取较长的一边
        long_side = max(width, height)
        
        # 如果已经小于目标尺寸，不需要缩放
        if long_side <= target_long_side:
            return None
            
        # 计算缩放比例
        scale_ratio = target_long_side / long_side
        
        # 计算新尺寸，确保是偶数（FFmpeg 要求）
        new_width = int(width * scale_ratio)
        new_height = int(height * scale_ratio)
        
        # 确保宽高都是偶数
        new_width = new_width if new_width % 2 == 0 else new_width - 1
        new_height = new_height if new_height % 2 == 0 else new_height - 1
        
        return f"{new_width}:{new_height}"
    
    def compress_video(self, input_path, output_path, status_callback=None):
        """
        压缩视频
        
        Args:
            input_path: 输入视频路径
            output_path: 输出视频路径
            status_callback: 状态回调函数，接收状态字符串参数
        
        Returns:
            bool: 压缩是否成功
        """
        try:
            # 设置状态为压缩中
            if status_callback:
                status_callback("compacting")
            
            # 获取视频信息
            video_info = self.get_video_info(input_path)
            if not video_info:
                log.error("无法获取视频信息")
                return False
                
            # 计算缩放参数
            scale = self.calculate_scale(video_info['width'], video_info['height'])
            
            # 构建 FFmpeg 命令
            params = [FFMPEG] + LOGLEVEL + ['-y', '-i', input_path]
            
            # 视频编码参数
            if scale:
                # 需要缩放
                params.extend(['-vf', f'scale={scale}'])
            
            # 设置码率为 2M
            params.extend(['-b:v', '2M'])
            
            # 音频直接复制，不重新编码
            params.extend(['-c:a', 'copy'])
            
            # 输出文件
            params.extend(['--', output_path])
            
            log.info(f"开始压缩视频: {input_path} -> {output_path}")
            if scale:
                log.info(f"视频将从 {video_info['width']}x{video_info['height']} 缩放到 {scale}")
            else:
                log.info("视频尺寸已经足够小，仅调整码率")
                
            # 执行压缩
            result = subprocess.run(params, stdin=STDIN, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            
            if result.returncode == 0:
                log.info("视频压缩成功")
                # 设置状态为完成
                if status_callback:
                    status_callback("完成")
                return True
            else:
                log.error(f"视频压缩失败: {result.stderr}")
                return False
                
        except Exception as e:
            log.error(f"视频压缩过程出错: {e}")
            return False

def compress_xiaohongshu_video(video_path, status_callback=None):
    """
    压缩小红书视频的便捷函数
    
    Args:
        video_path: 原始视频路径
        status_callback: 状态回调函数
        
    Returns:
        str: 压缩后的视频路径，失败返回 None
    """
    try:
        compressor = VideoCompressor()
        
        # 构建文件名
        dir_path = os.path.dirname(video_path)
        base_name = os.path.basename(video_path)
        name_parts = os.path.splitext(base_name)
        
        # 添加 _original 后缀到原文件
        original_path = os.path.join(dir_path, f"{name_parts[0]}_original{name_parts[1]}")
        
        # 压缩后的文件路径（添加 _compacted 后缀）
        compact_path = os.path.join(dir_path, f"{name_parts[0]}_compacted{name_parts[1]}")
        
        # 重命名原文件
        os.rename(video_path, original_path)
        log.info(f"原视频已重命名为: {original_path}")
        
        # 压缩视频
        success = compressor.compress_video(original_path, compact_path, status_callback)
        
        if success:
            # 删除原视频
            os.remove(original_path)
            log.info(f"已删除原视频: {original_path}")
            
            # 保留 _compacted 后缀，不重命名
            log.info(f"压缩视频已保存为: {compact_path}")
            
            return compact_path
        else:
            # 压缩失败，恢复原文件名
            os.rename(original_path, video_path)
            log.error("压缩失败，已恢复原文件名")
            return None
            
    except Exception as e:
        log.error(f"压缩小红书视频出错: {e}")
        # 尝试恢复原文件
        if os.path.exists(original_path) and not os.path.exists(video_path):
            os.rename(original_path, video_path)
        return None