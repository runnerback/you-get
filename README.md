# you-get（runnerback fork）

- **版本**: v1.0
- **更新时间**: 2026-05-25
- **上游**: [soimort/you-get](https://github.com/soimort/you-get)（develop 分支）
- **本 fork 用途**: 在原版基础上为 MediaCrawlerPro 项目增量集成快代理、字幕下载等能力

---

## 一、本 fork 相对上游的增量能力

| 能力 | 状态 | 说明 |
|---|---|---|
| 快代理（KuaiDaili）集成 | ✅ 已合入 | 默认启用；`--disable-kuaidaili-proxy` 关闭。⚠️ 当前硬编码的默认凭证返回的 IP 已被 B 站 ban，需自备凭证或关闭 |
| Bilibili 音视频分流下载 | ✅ 原生支持 | 用上游已有的 `-n / --no-merge`，产物为 `{title}[00].mp4`（视频）+ `{title}[01].mp4`（音频） |
| **Bilibili CC 字幕下载（含 AI）** | ✅ 本 fork 新增 | 需 `MediaCrawlerPro-SignSrv` 提供 wbi 签名；详见 §四 |
| 弹幕下载 | ✅ 原生 | 产物 `{title}.cmt.xml` |

---

## 二、安装与启动

```bash
cd /path/to/you-get

# 创建虚拟环境
python3 -m venv venv
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 验证
./you-get --version
```

依赖：
- Python ≥ 3.9（推荐 3.12，本 fork 实测 3.12.2）
- `ffmpeg`（合并音视频、检测大小；即使 `-n` 不合并也建议安装）
- `dukpy`（已在 requirements.txt）

---

## 三、Bilibili 基础下载

### 查看可用清晰度
```bash
./you-get --disable-kuaidaili-proxy -i https://www.bilibili.com/video/BVxxxxxx/
```

### 默认下载（合并为单个 mp4）
```bash
./you-get --disable-kuaidaili-proxy --cookies ~/bili_cookies.txt \
  --format=dash-flv720-AVC \
  https://www.bilibili.com/video/BVxxxxxx/
```

### ⚠️ Cookies 说明
- **480P 及以下**：无需 cookies
- **720P 及以上**：必须 `--cookies cookies.txt`（Netscape 格式，含 `SESSDATA`）
- 用浏览器扩展 "Get cookies.txt LOCALLY" 导出

### ⚠️ 快代理说明
本 fork 默认启用快代理，但 `kuaidaili_proxy.py` 里硬编码的默认凭证拿到的 IP **已被 B 站 ban**：
```text
[快代理] 正在使用快代理IP: http://...@218.95.37.11:14894
you-get: [error] oops, something went wrong.
```

解决方法：
1. **直连（推荐）**：加 `--disable-kuaidaili-proxy`
2. **自备凭证**：设环境变量 `KDL_SECERT_ID` / `KDL_SIGNATURE` / `KDL_USER_NAME` / `KDL_USER_PWD`
3. ⚠️ 代码里 `kuaidaili_proxy.py:280-283` 的硬编码兜底违反 "不要写保底代码,有问题及时暴露" 规则，待后续移除

---

## 四、Bilibili 字幕下载（含 AI 字幕，本 fork 新增）

### 前置：启动 SignSrv
```bash
cd /path/to/MediaCrawlerPro-SignSrv
venv/bin/python app.py    # 监听 8989
# 验证：curl http://127.0.0.1:8989/signsrv/pong
```

### 使用
字幕会**自动随视频下载**，无需额外参数（只要 SignSrv 在线 + 传了 cookies）：

```bash
./you-get --disable-kuaidaili-proxy --cookies ~/bili_cookies.txt \
  -n https://www.bilibili.com/video/BVxxxxxx/
```

### 产物
| 文件 | 说明 |
|---|---|
| `{title}.zh-CN.srt` | UP 上传的中文字幕 |
| `{title}.en-US.srt` | UP 上传的英文字幕 |
| `{title}.ai-zh-CN.srt` | AI 自动生成的中文字幕 |
| `{title}.ai-en-US.srt` | AI 自动生成的英文字幕 |

### 字幕失败时的行为（字幕是增量功能，绝不阻塞视频下载）
| 场景 | 表现 |
|---|---|
| SignSrv 未启动 | `[WARNING] [Subtitle] SignSrv 不可达 (http://127.0.0.1:8989)，跳过字幕下载` |
| cookies 未传 | `[WARNING] [Subtitle] 未提供 cookies，跳过字幕下载` |
| 视频无 CC 字幕 | `[INFO] [Subtitle] 该视频无可用字幕` |
| 签名 / 接口报错 | `[ERROR] [Subtitle] ...`，跳过字幕，视频继续 |

### 关闭字幕下载
复用上游已有 `--no-caption`，会同时关闭弹幕和字幕：
```bash
./you-get --no-caption ...
```

### SignSrv 地址配置
默认 `http://127.0.0.1:8989`，可用环境变量覆盖：
```bash
export SIGN_SRV_URL=http://other-host:8989
```

---

## 五、Bilibili 音视频分流（不合并）

详细见 [`docs/bilibili_no_merge_usage.md`](docs/bilibili_no_merge_usage.md)。

最小命令：
```bash
./you-get --disable-kuaidaili-proxy -n https://www.bilibili.com/video/BVxxxxxx/
```

产物：
- `{title}[00].mp4` — 视频流（hevc/avc/av1，无音轨）
- `{title}[01].mp4` — 音频流（aac）
- `{title}.cmt.xml` — 弹幕
- `{title}.{lang}.srt` — 字幕（若有 + SignSrv 在线）

下游辨别音视频建议用 `ffprobe ... | grep codec_type`，不要依赖 `[00]/[01]` 索引（上游升级可能改变）。

---

## 六、测试

项目用 stdlib `unittest`。跑全部测试：

```bash
venv/bin/python -m unittest discover tests -v
```

字幕模块的端到端验证（需 SignSrv + cookies）：
```bash
venv/bin/python tests/manual_test_bili_subtitle.py \
  --cookies ~/bili_cookies.txt --bv BVxxxxxx
```

---

## 七、新增文件清单

```
src/you_get/util/
    signsrv_client.py          # SignSrv HTTP 客户端
    kuaidaili_proxy.py         # 快代理客户端（含跨进程缓存）
src/you_get/extractors/
    bilibili_subtitle.py       # B 站字幕：抓取 + JSON→SRT + AI 判定
src/you_get/extractors/bilibili.py    # 修改：3 处 cid 旁加 fetch_subtitles(self, avid, cid)
tests/
    test_signsrv_client.py     # SignSrv 客户端单测（mock HTTP）
    test_bilibili_subtitle.py  # 字幕纯函数单测
    manual_test_bili_subtitle.py  # e2e 验证脚本
docs/
    bilibili_no_merge_usage.md     # 音视频分流用法
    superpowers/specs/2026-05-25-bili-subtitle-design.md   # 字幕设计 spec
    superpowers/plans/2026-05-25-bili-subtitle.md          # 字幕实现 plan
```

---

## 八、上游 / 许可

- 本 fork 保留上游 MIT 许可
- 上游项目：https://github.com/soimort/you-get
