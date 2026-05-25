# Bilibili 音视频分流下载（不合并）

- **版本**: v2.0
- **更新时间**: 2026-05-25
- **适用范围**: Bilibili DASH 流（默认大部分 BV/AV 视频走此协议）

---

## 一、场景

下载 B 站视频时，希望**保留原始音频流和视频流的分离文件**，不让 you-get 用 ffmpeg 合并成单个 mp4。常见用途：
- 音频流单独喂给 ASR / 转写服务
- 视频流单独做压缩、转码、抽帧
- 分发到不同的下游处理 pipeline

## 二、核心机制

**结论：you-get 已内置 `-n` / `--no-merge` 参数，无需改代码即可实现分流存储。**

源码位置：
- `src/you_get/common.py:1887` — `'-n', '--no-merge'` 参数定义
- `src/you_get/common.py:1336-1338` — `if not merge: return` 跳过合并
- `src/you_get/common.py:1340-1348` — `merge=True` 时才调 `ffmpeg_concat_av` 合并并删除分片

## 三、基础命令

```bash
cd /path/to/you-get
source venv/bin/activate

# 最小命令（依赖 .env 里配好 RESOURCE_SRV_URL；cookies 自动从资源服务拉）
./you-get -n https://www.bilibili.com/video/BVxxxxxx

# 显式禁用资源服务代理 + 自己传 cookies
./you-get -n --disable-srv-proxy --cookies ~/bili_cookies.txt \
  https://www.bilibili.com/video/BVxxxxxx

# 指定清晰度
./you-get -n --format=dash-flv720-AVC https://www.bilibili.com/video/BVxxxxxx
```

## 四、产物文件（实测）

下载 `BV1GJ411x7h7` 360P HEVC 后：

| 文件 | 媒体类型（ffprobe） | 编码 | 典型大小 |
|---|---|---|---|
| `{title}[00].mp4` | **video** | hevc / avc / av1 | 视频流主体 |
| `{title}[01].mp4` | **audio** | aac | 视频流的 ~1/4 |
| `{title}.cmt.xml` | 弹幕（XML） | — | KB 级 |
| `{title}.{lan}.srt` | UP 上传字幕 | — | 仅当视频有字幕 |
| `{title}.ai-{lan}.srt` | AI 生成字幕 | — | 仅当 AI 字幕开启 |

### 文件命名规律
- 同一 `{title}` 前缀（非法字符已替换）
- `[NN]` 是分片索引：
  - **`[00]` = 视频流**（`bilibili.py` 里 video 列表先 append）
  - **`[01]` = 音频流**（audio 列表后 append）
- 扩展名统一是 `.mp4`（DASH container），但实际编码不同
- 字幕详见 [`../README.md` §四](../README.md)

### 下游辨别音视频的可靠方式

```bash
# 推荐：用 ffprobe 取 codec_type
ffprobe -v error -show_streams -of default=noprint_wrappers=1 file.mp4 \
  | grep codec_type
# 输出：codec_type=video  或  codec_type=audio

# 不推荐：按 [00]/[01] 索引（依赖 you-get 当前实现，长期可能变）
```

## 五、依赖与前置条件

| 项 | 是否必需 | 说明 |
|---|---|---|
| Python venv | 必需 | `venv/bin/python` ≥ 3.9（实测 3.12.2） |
| `ffmpeg` | 强烈推荐 | 即使 `-n` 不合并，you-get 内部仍可能调 `ffprobe` 取大小 |
| **登录 cookies** | **720P+ 必需** | 三种获取方式见 [`../README.md` §三](../README.md) |
| SignSrv 在线 | 字幕需要 | 见 [`../README.md` §四](../README.md) |
| 网络可直连 B 站 | 必需 | 资源服务代理 IP 可能被 B 站拦截，加 `--disable-srv-proxy` |

## 六、可用清晰度查询

下载前先用 `-i` 查可用 DASH 格式：
```bash
./you-get --disable-srv-proxy -i https://www.bilibili.com/video/BVxxxxxx
```

输出会列出所有可用 `format`（如 `dash-flv360-HEVC`、`dash-flv720-AVC`、`dash-flv1080-AV1`），按需 `--format=` 指定。

## 七、已知限制

- 仅适用于 **DASH 流**（B 站现在的主流协议）
- 弹幕文件 `.cmt.xml` 总是会下载，如不需要加 `--no-caption`（会同时关闭字幕）
- 外挂 SRT 字幕需视频本身有 UP/AI 字幕；详见 [`../README.md` §四](../README.md)
