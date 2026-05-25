# you-get 下载 Bilibili 视频：音视频分流（不合并）使用说明

- **版本**: v1.0
- **更新时间**: 2026-05-25
- **适用范围**: Bilibili DASH 流（默认大部分 BV/AV 视频走此协议）
- **基于实测**: 2026-05-25 用 `BV1GJ411x7h7`（5MB 360P HEVC）实测验证

---

## 一、场景

下载 B 站视频时，希望**保留原始音频流和视频流的分离文件**，不让 you-get 用 ffmpeg 合并成一个 mp4。常见用途：
- 音频流单独喂给 ASR / 转写服务
- 视频流单独做压缩、转码、抽帧
- 分发到不同的下游处理 pipeline

---

## 二、核心机制

**结论：you-get 已内置 `-n` / `--no-merge` 参数，无需改代码即可实现分流存储。**

源码佐证（`src/you_get/common.py`）：
- `1887`: `'-n', '--no-merge'` 参数定义
- `1336-1338`: `if not merge: print(); return` — 下载完分片直接返回，不调 ffmpeg 合并
- `1340-1348`: `merge=True` 时才调 `ffmpeg_concat_av` 合并并删除分片

---

## 三、基础命令

```bash
# 切到 you-get 目录、激活 venv
cd /Users/zhangjianbo/Documents/MediaCrawlerPro/you-get
source venv/bin/activate

# 最小命令：分流下载到当前目录
./you-get -n https://www.bilibili.com/video/BVxxxxxx/

# 推荐命令：指定输出目录、格式、cookies（720P+ 必需）
./you-get -n \
  -o /path/to/output \
  --format=dash-flv720-AVC \
  --cookies ~/path/to/cookies.txt \
  --disable-kuaidaili-proxy \
  https://www.bilibili.com/video/BVxxxxxx/
```

---

## 四、产出文件命名规则（实测验证）

下载 `BV1GJ411x7h7` 360P HEVC 后的产物：

| 文件 | 媒体类型（ffprobe） | 编码 | 大小 |
|---|---|---|---|
| `{title}[00].mp4` | **video** | hevc, 640×360 | 4.0 MB |
| `{title}[01].mp4` | **audio** | aac | 1.1 MB |
| `{title}.cmt.xml` | 弹幕（XML） | — | 126 KB |

### 命名规律
- 同一 `{title}` 前缀（已替换非法字符）
- `[NN]` 是分片索引：
  - **`[00]` = 视频流**（`bilibili.py` 里 video 列表先 append）
  - **`[01]` = 音频流**（audio 列表后 append）
- 扩展名统一是 `.mp4`（DASH container），但**实际编码不同**（视频是 H.264/H.265/AV1，音频是 AAC）
- 弹幕文件：`{title}.cmt.xml`（无 `[NN]` 后缀）

### 下游辨别视频/音频的可靠方式

```bash
# 1. 按索引（依赖 you-get 当前行为，长期可能变）
{title}[00].mp4  # 视频
{title}[01].mp4  # 音频

# 2. 用 ffprobe 取 codec_type（推荐，最稳）
ffprobe -v error -show_streams -of default=noprint_wrappers=1 file.mp4 \
  | grep codec_type
# 输出：codec_type=video  或  codec_type=audio

# 3. 按大小：视频通常远大于音频（5MB 视频里 4MB 视频 + 1MB 音频）
```

---

## 五、依赖与前置条件

| 项 | 是否必需 | 说明 |
|---|---|---|
| Python venv | 必需 | `venv/bin/python` 已存在（3.12.2 实测） |
| `dukpy` | 必需 | `requirements.txt` 已声明 |
| `ffmpeg` | 强烈推荐 | 即使 `-n` 不合并，you-get 内部仍可能调 `ffprobe` 取文件大小、做完整性检查 |
| **登录 cookies** | **720P+ 必需** | 不传只能 480P 及以下；`bilibili.py:230` 明确警告 |
| 网络可直连 B 站 | 必需 | 见下方"快代理"小节 |

### Cookies 获取
浏览器装 "Get cookies.txt LOCALLY" 扩展（Chrome / Edge），登录 B 站后导出 `bilibili.com` 的 cookies.txt（Netscape 格式，含 `SESSDATA`）。

---

## 六、⚠️ 快代理问题（实测发现）

`you-get` 默认启用快代理（`common.py:1990` `default=True`），实测**默认 IP 已被 B 站拦截**，会导致请求失败：

```text
you-get: [快代理] 正在使用快代理IP: http://d4348355574:gxqsl7gd@218.95.37.11:14894
you-get: [快代理] 快代理设置成功: 218.95.37.11:14894
you-get: [error] oops, something went wrong.
```

### 解决方案（选一）
1. **直连**（最简单，本地有 B 站访问能力时）：每次加 `--disable-kuaidaili-proxy`
2. **换有效快代理凭证**：设环境变量 `KDL_SECERT_ID` / `KDL_SIGNATURE` / `KDL_USER_NAME` / `KDL_USER_PWD`，覆盖代码里的硬编码默认值
3. **改源码**：把 `default=True` 改为 `default=False`（影响范围大，慎改）

### 关于硬编码兜底
`kuaidaili_proxy.py:280-283` 写了硬编码的 secret_id/signature 作为兜底，违反用户的 "不要写保底代码,有问题及时暴露" 规则。建议后续移除兜底，让配置缺失时直接 raise，避免出现"看起来连上代理但其实 IP 被 ban"的误导。

---

## 七、完整推荐命令模板

```bash
cd /Users/zhangjianbo/Documents/MediaCrawlerPro/you-get
source venv/bin/activate

./you-get \
  -n \                                     # 不合并音视频
  --disable-kuaidaili-proxy \              # 关闭已失效的快代理
  --cookies ~/bili_cookies.txt \           # 720P+ 必需
  --format=dash-flv1080_4k-AVC \           # 指定清晰度，先用 -i 查可用 format
  -o /Volumes/T2/DataCrawlerDatabase/bilibili_video/separated \
  https://www.bilibili.com/video/BVxxxxxx/
```

---

## 八、可用清晰度查询

下载前先用 `-i` 查可用 DASH 格式：
```bash
./you-get --disable-kuaidaili-proxy -i https://www.bilibili.com/video/BVxxxxxx/
```

输出会列出所有可用 `format`（如 `dash-flv360-HEVC`、`dash-flv720-AVC`、`dash-flv1080-AV1` 等），按需 `--format=` 指定。

---

## 九、与 MediaCrawlerPro 集成建议

如要把 you-get 分流下载集成进 `MediaCrawlerPro-Python` 或 `DataCrawlerWebStation`：

1. **路径**：通过 `app.utils.path_helper.get_data_crawler_path()` 拼输出路径（遵守项目路径规范）
2. **辨别音视频**：用 `ffprobe` 的 `codec_type` 判断，**不要**依赖 `[00]`/`[01]` 索引（you-get 后续升级可能变命名）
3. **错误暴露**：捕获 you-get 退出码非 0 时立即 raise，**不要**写 fallback
4. **代理**：建议总是加 `--disable-kuaidaili-proxy`，统一在外层用你自己的代理体系

---

## 十、已知限制

- 仅适用于 **DASH 流**（B 站现在的主流协议）。如视频走 FLV 多段，`-n` 同样不合并，但产物是多段 FLV 而不是音视频分离
- 弹幕文件 `.cmt.xml` 总是会下载，如不需要可加 `--no-caption`
- 字幕（外挂 SRT）需要视频本身有上传，本次实测视频无字幕
