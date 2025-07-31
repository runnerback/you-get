# you-get 文档目录

欢迎查阅 you-get 的文档和示例代码。

## 文档列表

### 功能文档
- [小红书（Xiaohongshu）支持文档](./xiaohongshu-support.md) - 小红书平台的下载功能说明和使用方法

### 开发文档
- [集成指南](./integration-guide.md) - 如何在 Python 服务中集成 you-get

## 示例代码

所有示例代码都在 `examples/` 目录下：

### 测试示例
- [test_xiaohongshu.py](./examples/test_xiaohongshu.py) - 小红书功能的完整测试套件
- [test_return_code.py](./examples/test_return_code.py) - 测试返回值机制和错误处理

### 集成示例
- [you_get_service_example.py](./examples/you_get_service_example.py) - 完整的服务集成示例，包含下载器封装类

### 其他示例
- [test_batch_download.py](./examples/test_batch_download.py) - 批量下载功能测试（如果存在）
- [test_xhs_video.py](./examples/test_xhs_video.py) - 小红书视频下载测试（如果存在）

## 快速上手

### 1. 下载小红书图片
```bash
you-get 'https://sns-webpic-qc.xhscdn.com/xxx!nd_dft_wlteh_jpg_3'
```

### 2. 下载小红书视频
```bash
you-get 'http://sns-video-bd.xhscdn.com/xxx'
```

### 3. 批量下载（逗号分隔）
```bash
you-get 'url1,url2,url3'
```

### 4. 在 Python 中使用
```python
import subprocess

result = subprocess.run(['you-get', url], capture_output=True)
if result.returncode == 0:
    print("下载成功")
```

## 注意事项

1. **Shell 特殊字符**：在 zsh 中使用单引号包围含有 `!` 的 URL
2. **代理问题**：小红书会自动禁用代理以避免 403 错误
3. **返回值**：返回码 0 表示成功，非 0 表示失败

## 更多信息

- 主项目：[you-get](https://github.com/soimort/you-get)
- 问题反馈：[Issues](https://github.com/soimort/you-get/issues)

## 更新日志

### 2025-07-31
- 新增小红书图片和视频下载支持
- 新增批量下载功能
- 添加完整的文档和示例代码