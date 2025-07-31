# 小红书（Xiaohongshu）支持文档

本文档介绍 you-get 对小红书平台的支持情况和使用方法。

## 功能特性

### 支持的内容类型

1. **图片下载**
   - 支持所有小红书图片 CDN 域名（sns-webpic-qc、sns-img-qc、sns-img-hw、sns-img-bd、sns-img-qn）
   - 自动识别图片格式（jpg、png、webp）
   - 处理特殊的图片后缀（如 `!nd_dft_wlteh_jpg_3`）

2. **视频下载**
   - 支持所有小红书视频 CDN 域名（sns-video-bd、sns-video-qc、sns-video-hw、sns-video-qn）
   - 下载为 MP4 格式
   - 支持高清视频（如 1080p HEVC 编码）

3. **批量下载**
   - 支持逗号分隔的多个 URL
   - 支持空格分隔的多个 URL
   - 支持从文件读取 URL 列表

### 技术特性

1. **防盗链处理**
   - 自动设置正确的 Referer 头（`https://www.xiaohongshu.com/`）
   - 设置必要的请求头模拟浏览器访问

2. **代理处理**
   - 自动检测并临时禁用代理（避免 CDN 拒绝代理 IP）
   - 下载完成后恢复原始代理设置

## 使用方法

### 基本用法

#### 下载单个图片
```bash
you-get 'https://sns-webpic-qc.xhscdn.com/xxx!nd_dft_wlteh_jpg_3'
```

#### 下载单个视频
```bash
you-get 'http://sns-video-bd.xhscdn.com/xxx'
```

### 批量下载

#### 方法1：逗号分隔
```bash
you-get 'url1,url2,url3'
```

#### 方法2：空格分隔
```bash
you-get 'url1' 'url2' 'url3'
```

#### 方法3：从文件读取
```bash
# urls.txt 文件中每行一个 URL
you-get -i urls.txt
```

### 高级选项

#### 指定输出目录
```bash
you-get -o /path/to/output 'https://xxx'
```

#### 指定输出文件名
```bash
you-get -O my_video.mp4 'https://xxx'
```

#### 获取媒体信息（不下载）
```bash
you-get -i 'https://xxx'
```

#### 获取 JSON 格式信息
```bash
you-get --json 'https://xxx'
```

## 注意事项

### Shell 特殊字符处理

在 zsh 中，URL 中的 `!` 字符会被解释为历史扩展符号，需要特殊处理：

1. **使用单引号（推荐）**
   ```bash
   you-get 'https://xxx!nd_dft_wlteh_jpg_3'
   ```

2. **转义感叹号**
   ```bash
   you-get https://xxx\!nd_dft_wlteh_jpg_3
   ```

3. **临时禁用历史扩展**
   ```bash
   set +H
   you-get "https://xxx!nd_dft_wlteh_jpg_3"
   set -H
   ```

### 代理相关

- 小红书 CDN 会拒绝来自已知代理 IP 的请求
- you-get 会自动检测并临时禁用代理
- 如果仍然遇到 403 错误，可以手动禁用代理：
  ```bash
  unset http_proxy https_proxy
  you-get 'https://xxx'
  ```

### 错误处理

常见错误及解决方法：

1. **403 Forbidden**
   - 原因：代理 IP 被拒绝或请求头不正确
   - 解决：确保使用最新版本，代理会自动禁用

2. **"不支持的小红书URL格式"**
   - 原因：URL 格式不是直链
   - 解决：确保使用的是 CDN 直链，不是笔记页面 URL

3. **下载超时**
   - 原因：网络问题或文件过大
   - 解决：检查网络连接，使用 `--timeout` 参数增加超时时间

## 返回值说明

you-get 使用标准的进程返回码：

- `0`: 下载成功
- `1`: 一般错误（网络错误、不支持的URL等）
- `2`: 参数错误
- 其他: 系统错误

在程序中集成时，可以通过检查返回码判断是否成功：

```python
import subprocess

result = subprocess.run(['you-get', url], capture_output=True)
if result.returncode == 0:
    print("下载成功")
else:
    print(f"下载失败，错误码: {result.returncode}")
```

## 示例代码

完整的集成示例请参考：
- [简单测试示例](./examples/test_xiaohongshu.py)
- [批量下载示例](./examples/test_batch_download.py)  
- [服务集成示例](./examples/you_get_service_example.py)
- [返回值测试示例](./examples/test_return_code.py)

## 更新日志

### 2025-07-31
- 新增小红书图片直接下载支持
- 新增小红书视频直接下载支持
- 新增批量下载功能（支持逗号分隔的 URL）
- 自动处理防盗链和代理问题
- 添加完整的文档和示例代码