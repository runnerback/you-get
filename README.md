# you-get（runnerback fork）

- **版本**: v1.3
- **更新时间**: 2026-05-25
- **上游**: [soimort/you-get](https://github.com/soimort/you-get)（develop 分支）
- **本 fork 用途**: 视频/音频/弹幕/字幕下载工具；签名走 SignSrv、cookies/代理走 MediaCrawlerPro-Python 资源服务

> 📖 配套文档：[`CLAUDE.md`](CLAUDE.md) · [`docs/bilibili-no-merge.md`](docs/bilibili-no-merge.md) · [`.env.example`](.env.example)

## 服务架构概览

```
┌──────────────────────────┐  签名/wbi   ┌─────────────────────────────────┐
│ you-get (CLI 下载工具)   │ ─────────► │ MediaCrawlerPro-SignSrv (:8989) │
│                          │            │  • 算 wts/w_rid 签名             │
│                          │            │  • 维护 wbi key（每天换）        │
│                          │            └─────────────────────────────────┘
│                          │  cookies   ┌─────────────────────────────────┐
│                          │ ─────────► │ MediaCrawlerPro-Python (:8990)  │
│                          │            │  • GET /api/v1/{platform}/cookies│
└──────────────────────────┘            │    → 查 crawler_cookies_account │
                                        │  • CLI 入口仍为 main.py 不变    │
                                        └─────────────────────────────────┘
```

---

## 一、本 fork 相对上游的增量能力

| 能力 | 状态 | 说明 |
|---|---|---|
| 代理（共享代理池） | ✅ v1.2 重构 | **快代理具体实现已彻底移除**，统一由 `MediaCrawlerPro-Python` 资源服务提供 `GET /api/v1/proxy/kuaidaili`。默认启用；`--disable-srv-proxy` 关闭。旧参数 `--disable-srv-proxy` 作为别名保留 |
| Bilibili 音视频分流下载 | ✅ 原生支持 | 用上游已有的 `-n / --no-merge`，产物为 `{title}[00].mp4`（视频）+ `{title}[01].mp4`（音频） |
| **Bilibili CC 字幕下载（含 AI）** | ✅ 本 fork 新增 | 需 `MediaCrawlerPro-SignSrv` 提供 wbi 签名；详见 §四 |
| Cookies 自动从资源服务拉取 | ✅ 本 fork 新增 | 未传 `--cookies` 时自动调 `MediaCrawlerPro-Python` 资源服务 `GET /api/v1/bili/cookies` |
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
./you-get --disable-srv-proxy -i https://www.bilibili.com/video/BVxxxxxx/
```

### 默认下载（合并为单个 mp4）
```bash
./you-get --disable-srv-proxy --cookies ~/bili_cookies.txt \
  --format=dash-flv720-AVC \
  https://www.bilibili.com/video/BVxxxxxx/
```

### ⚠️ Cookies 说明
- **480P 及以下**：无需 cookies
- **720P 及以上 / CC 字幕**：需要含 `SESSDATA` 的 cookies。支持两种来源（优先级从高到低）：
  1. `--cookies cookies.txt`（Netscape 格式）— 浏览器扩展 "Get cookies.txt LOCALLY" 导出
  2. **从 MediaCrawlerPro-Python 资源服务自动拉取**（推荐，零配置）：
     - 启动 MediaCrawlerPro-Python 资源服务（`python serve.py`，默认 8990）
     - DB 表 `crawler_cookies_account` 里有 `status=0` 的 bili cookies 即可
     - you-get 启动时若发现没传 `--cookies`，自动调 `GET http://127.0.0.1:8990/api/v1/bili/cookies` 拉取
     - 资源服务地址用环境变量 `RESOURCE_SRV_URL` 配置（在 `.env` 里）

### 代理（v1.2 重构后）
本 fork 默认从 `MediaCrawlerPro-Python` 资源服务（默认 `http://127.0.0.1:8990`）拉代理。

| 场景 | 行为 |
|---|---|
| 资源服务返回代理 | log 输出 `[Proxy] 使用资源服务代理: http://...`，注入 urllib |
| 资源服务返回 500 / 不可达 / 端点 KDL 凭证未配 | `[Proxy] 资源服务未返回可用代理` → 降级直连，不阻塞下载 |
| 显式禁用 | `--disable-srv-proxy`（旧别名 `--disable-srv-proxy` 仍可用） |
| 自传代理 | `--http-proxy HOST:PORT` 或 `-s/--socks-proxy HOST:PORT` 优先级最高 |

资源服务端的 KDL 凭证在 `MediaCrawlerPro-Python/.env` 配置：
```bash
KDL_SECRET_ID=...
KDL_SIGNATURE=...
KDL_USER_NAME=...
KDL_USER_PWD=...
```
未配置时端点返回 500，you-get 自动降级直连（不写硬编码兜底，问题及时暴露）。

---

## 四、Bilibili 字幕下载（含 AI 字幕，本 fork 新增）

### 前置：启动两个服务

```bash
# 1. SignSrv（必需，提供 wbi 签名）
cd /path/to/MediaCrawlerPro-SignSrv
venv/bin/python app.py    # 监听 8989
# 验证：curl http://127.0.0.1:8989/signsrv/pong

# 2. MediaCrawlerPro-Python 资源服务（可选，提供 DB cookies）
#    不启则必须传 --cookies cookies.txt
cd /path/to/MediaCrawlerPro-Python
venv/bin/python serve.py    # 监听 8990
# 验证：curl http://127.0.0.1:8990/health
```

### 使用
字幕会**自动随视频下载**：

```bash
# 零配置（用 DB cookies + 自动签名）
./you-get --disable-srv-proxy -n https://www.bilibili.com/video/BVxxxxxx/

# 显式传 cookies（覆盖 DB cookies）
./you-get --disable-srv-proxy --cookies ~/bili_cookies.txt \
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
| SignSrv 未启动 | `[WARNING] [Subtitle] SignSrv 不可达 (...)，跳过字幕下载` |
| 没传 cookies 且资源服务不可达 / 无可用 cookies | `[WARNING] [Subtitle] 未提供 cookies 且资源服务无可用 cookies，跳过字幕下载` |
| 从资源服务拉到 cookies | `[INFO] [Subtitle] 已从资源服务获取 bili cookies` |
| 视频无 CC 字幕 | `[INFO] [Subtitle] 该视频无可用字幕` |
| 签名 / 接口报错 | `[ERROR] [Subtitle] ...`，跳过字幕，视频继续 |

### 关闭字幕下载
复用上游已有 `--no-caption`，会同时关闭弹幕和字幕：
```bash
./you-get --no-caption ...
```

### 环境变量配置（`.env` 文件）

项目根目录支持 `.env` / `.env.production` / `.env.example`：

```bash
cp .env.example .env   # 复制模板，按需修改
```

`.env` 内容：
```bash
SIGN_SRV_URL=http://127.0.0.1:8989
RESOURCE_SRV_URL=http://127.0.0.1:8990
```

`APP_ENV=production` 启动时会读 `.env.production`；shell 已有的环境变量优先级最高。

---

## 五、Bilibili 音视频分流（不合并）

详细见 [`docs/bilibili-no-merge.md`](docs/bilibili-no-merge.md)。

最小命令：
```bash
./you-get --disable-srv-proxy -n https://www.bilibili.com/video/BVxxxxxx/
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
    cookies_srv_client.py      # 从资源服务拉 cookies
    proxy_srv_client.py        # 从资源服务拉代理 URL（v1.2 新增）
    # ❌ kuaidaili_proxy.py 已删除（v1.2），统一由资源服务提供代理
src/you_get/extractors/
    bilibili_subtitle.py       # B 站字幕：抓取 + JSON→SRT + AI 判定
src/you_get/extractors/bilibili.py    # 修改：3 处 cid 旁加 fetch_subtitles(self, avid, cid)
tests/
    test_signsrv_client.py     # SignSrv 客户端单测（mock HTTP）
    test_bilibili_subtitle.py  # 字幕纯函数单测
    manual_test_bili_subtitle.py  # e2e 验证脚本
docs/
    bilibili-no-merge.md     # 音视频分流用法详解
```

---

## 八、上游 / 许可

- 本 fork 保留上游 MIT 许可
- 上游项目：https://github.com/soimort/you-get
