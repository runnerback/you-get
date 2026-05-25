# Bilibili CC 字幕下载（含 AI 字幕）设计文档

- **版本**: v1.0
- **创建时间**: 2026-05-25
- **作者**: Claude（基于用户 brainstorm 决策）
- **依赖项目**: `MediaCrawlerPro-SignSrv`（必需，未启动则跳过字幕）

---

## 一、背景

`you-get` 的 `media_platform/extractors/bilibili.py` 目前只下载弹幕（`comment.bilibili.com/{cid}.xml` → `{title}.cmt.xml`），**未实现 CC 字幕下载**。通用框架已支持字幕落盘（`extractor.py:244-255`），只要 extractor 往 `self.caption_tracks[key]` 塞 SRT 字符串，主流程会自动写成 `{title}.{key}.srt`。

本设计补齐 bilibili 的字幕抓取链路，包含：
- UP 主上传字幕
- B 站 AI 自动生成字幕

---

## 二、目标与非目标

### 目标
1. 下载视频时同时下载该视频所有可用 CC 字幕（含 AI）
2. SignSrv 未启动 / cookies 缺失时，warn 后跳过字幕，**不影响视频和其他产物下载**
3. 多语言字幕用 `{lang}` 区分，AI 字幕用 `ai-{lang}` 前缀区分，避免覆盖
4. 复用 `extractor.py` 通用字幕落盘机制，**不**改动主流程

### 非目标
- 不实现 SignSrv 内部的 wbi 签名（SignSrv 端 `apis/bilibili.py` 已实现，直接 HTTP 调用即可）
- 不下载弹幕已有的功能（弹幕维持现状，不动）
- 不解决"快代理 IP 被 B 站 ban"的问题（与字幕无关，已记在 `docs/bilibili_no_merge_usage.md`）

---

## 三、架构

```
┌─────────────────────────────────────────────────────────────┐
│ bilibili.py prepare(self)                                    │
│  ... 现有 dash 解析 + danmaku 下载 ...                       │
│                                                              │
│  # NEW: 字幕抓取（3 处 cid 分支各加一行）                    │
│  self._fetch_subtitles_safe(avid, cid)                       │
└────────────────────────────────┬─────────────────────────────┘
                                 ↓
┌─────────────────────────────────────────────────────────────┐
│ NEW bilibili_subtitle.py                                     │
│  fetch_subtitles(self, avid, cid) -> None                    │
│    1. 前置检查：cookies 存在 + SignSrv 健康                  │
│       任一失败 → log.w + return（不抛错，不修改 self.caption_tracks）│
│    2. 调 SignSrv 拿 wts/w_rid                                 │
│    3. 调 https://api.bilibili.com/x/player/wbi/v2             │
│    4. 遍历 data.subtitle.subtitles[]                         │
│    5. 每条：                                                  │
│       - GET subtitle_url（B 站 JSON 字幕）                    │
│       - 转 SRT 格式                                           │
│       - key = "ai-" + lan if 是AI else lan                    │
│       - self.caption_tracks[key] = srt_string                │
└────────────────┬───────────────────────────┬─────────────────┘
                 ↓                           ↓
┌──────────────────────────────┐  ┌──────────────────────────────┐
│ NEW util/signsrv_client.py   │  │ extractor.py:244-255 (已有)   │
│  is_signsrv_available()      │  │  for lang in caption_tracks: │
│  call_bilibili_sign(req,ck)  │  │    写 {title}.{lang}.srt     │
│  - env: SIGN_SRV_URL          │  └──────────────────────────────┘
│  - default 127.0.0.1:8989    │
└──────────────────────────────┘
```

---

## 四、关键接口

### 4.1 SignSrv → bilibili 签名（已实现，本设计只消费）

```http
POST {SIGN_SRV_URL}/signsrv/v1/bilibili/sign
Content-Type: application/json

{"req_data": {"aid": "80433022", "cid": "137649199"}, "cookies": "<原始 cookie 字符串>"}
```

响应（已实测）：
```json
{"biz_code": 0, "msg": "success", "isok": true, "data": {"wts": "1779701373", "w_rid": "1d877b81b9966957157302cf96f4dd5e"}}
```

### 4.2 B 站字幕列表（已实测，无字幕视频返回空数组）

```http
GET https://api.bilibili.com/x/player/wbi/v2?aid={avid}&cid={cid}&wts={wts}&w_rid={w_rid}
User-Agent: Mozilla/5.0
Referer: https://www.bilibili.com/
Cookie: {原始 cookie 字符串}
```

响应（已实测路径，subtitle 子结构）：
```json
{
  "code": 0,
  "message": "OK",
  "data": {
    "subtitle": {
      "allow_submit": false,
      "lan": "",
      "lan_doc": "",
      "subtitles": [ /* 见 4.3，每项一个字幕 */ ],
      "subtitle_position": 0,
      "font_size_type": 0
    }
  }
}
```

### 4.3 subtitles[] 数组每项结构（**实测校准点 #1**）

基于 B 站公开 API 知识，字段如下（首次实跑时需用一个有字幕的视频校准）：

```json
{
  "id": 12345,
  "lan": "zh-CN",
  "lan_doc": "中文（中国）",
  "is_lock": false,
  "subtitle_url": "//aisubtitle.hdslb.com/bfs/ai_subtitle/...",
  "type": 1,            // 0=人工上传, 1=AI 自动生成
  "id_str": "12345",
  "ai_type": 0,
  "ai_status": 2
}
```

**AI 判定规则（实现时确认）**：`type == 1` 或 `ai_type > 0` 或 `ai_status > 0` 任一为真即视为 AI。具体以一次实跑数据为准，若三个字段都不可靠，则改成"lan 字段以 `ai-` 开头"判定。

### 4.4 字幕 JSON 文件结构（已知）

```json
{
  "font_size": 0.4,
  "font_color": "#FFFFFF",
  "background_alpha": 0.5,
  "background_color": "#9C27B0",
  "Stroke": "none",
  "body": [
    {"from": 0.0, "to": 2.5, "location": 2, "content": "字幕内容"},
    {"from": 2.5, "to": 5.0, "location": 2, "content": "下一段"}
  ]
}
```

转 SRT 算法：与 `youtube.py:294-311` 对应（秒数 → `HH:MM:SS,mmm`）。

---

## 五、模块与文件清单

### 5.1 新增文件

| 文件 | 职责 | 行数 |
|---|---|---|
| `src/you_get/util/signsrv_client.py` | SignSrv HTTP 客户端 | ~50 |
| `src/you_get/extractors/bilibili_subtitle.py` | 字幕抓取 + JSON→SRT 转换 | ~80 |

### 5.2 修改文件

| 文件 | 修改 | 行数 |
|---|---|---|
| `src/you_get/extractors/bilibili.py` | 3 处 `# get danmaku` 旁加 `_fetch_subtitles_safe(avid, cid)` | ~9 |

### 5.3 新增依赖

无（urllib + json 已足够，复用现有 `get_content`）。

---

## 六、设计细节

### 6.1 `signsrv_client.py` 接口

```python
# Pseudocode
SIGN_SRV_URL = os.environ.get("SIGN_SRV_URL", "http://127.0.0.1:8989")

def is_signsrv_available(timeout: float = 1.0) -> bool:
    """GET /signsrv/pong，HTTP 200 且 biz_code=0 视为可用。任何异常返回 False。"""

def call_bilibili_sign(req_data: dict, cookies: str, timeout: float = 5.0) -> dict | None:
    """POST /signsrv/v1/bilibili/sign。
    返回 {"wts": "...", "w_rid": "..."} 或 None（失败时）。
    失败原因：网络错误、HTTP 非 200、biz_code 非 0 — 均 log.e 后返回 None，**不抛异常**。
    """
```

设计要点：
- 不写"重试 N 次"等保底逻辑，单次失败直接返回 None（遵守"有问题及时暴露"原则）
- 所有失败 log.e 打日志便于排查
- 不缓存（每次都问 SignSrv，由 SignSrv 自己缓存 wbi key）

### 6.2 `bilibili_subtitle.py` 接口

```python
def fetch_subtitles(extractor, avid, cid, cookies: str) -> None:
    """抓取并填充 extractor.caption_tracks。
    任何失败（前置检查、签名、列表接口、单条字幕下载）都 log.w 后跳过对应步骤，
    不抛异常、不影响 caller。
    """
```

执行流程：
1. `cookies` 为空 → `log.w("[Subtitle] 未提供 cookies，跳过字幕下载")` → return
2. `not is_signsrv_available()` → `log.w("[Subtitle] SignSrv 不可达 ({SIGN_SRV_URL})，跳过字幕下载")` → return
3. `sign = call_bilibili_sign({"aid": str(avid), "cid": str(cid)}, cookies)` — None 则 return
4. 拼 URL → GET → 解析 `data.subtitle.subtitles[]`
5. 列表为空 → `log.i("[Subtitle] 无可用字幕")` → return
6. 遍历每条字幕：
   - 拼绝对 URL（`subtitle_url` 是 `//xxx` 形式，加 `https:` 前缀）
   - GET 拿 JSON → 解析 body → 转 SRT
   - 决定 key：AI 字幕 `ai-{lan}`，UP 上传 `{lan}`
   - **冲突处理**：同 key 已存在时 log.w 并跳过（不覆盖；正常情况不会冲突）
   - 单条字幕下载失败 → log.w（包含 lan 和原因）→ 继续下一条

### 6.3 `bilibili.py` 改动位置

`grep -n "get danmaku" src/you_get/extractors/bilibili.py` 找到 3 处，分别在：
- `337` (普通视频)
- `416` (番剧)
- `598` (festival)

每处的修改示例：
```python
# get danmaku
self.danmaku = get_content('https://comment.bilibili.com/%s.xml' % cid, headers=self.bilibili_headers(referer=self.url))

# NEW: get subtitles (via SignSrv)
from .bilibili_subtitle import fetch_subtitles
fetch_subtitles(self, avid, cid, cookies=load_cookies_string())
```

`load_cookies_string()` 是把全局 `cookies`（已由 `--cookies` 加载）拼成字符串的工具，可放在 `bilibili_subtitle.py` 内部实现（从 `you_get.common.cookies` 读 cookiejar 并 serialize）。

### 6.4 命名与冲突

| 字幕类型 | 文件名 |
|---|---|
| UP 上传中文 | `{title}.zh-CN.srt` |
| UP 上传英文 | `{title}.en-US.srt` |
| AI 中文 | `{title}.ai-zh-CN.srt` |
| AI 英文 | `{title}.ai-en-US.srt` |

如 B 站某天给 AI 字幕的 `lan` 直接返回 `ai-zh` 而非 `zh-CN` + `type=1`，则不会重复加前缀（实现里 `key = "ai-" + lan if is_ai and not lan.startswith("ai-") else lan`）。

### 6.5 错误处理矩阵

| 失败场景 | 行为 |
|---|---|
| cookies 未提供 | log.w + return（跳过字幕） |
| SignSrv 不可达 | log.w + return（跳过字幕） |
| SignSrv 签名 API 报错 | log.e + return（跳过字幕） |
| 字幕列表 API 返回 code != 0（如 -352 风控） | log.e + return（跳过字幕） |
| 字幕列表为空 | log.i + return（正常情况，许多视频无字幕） |
| 单条字幕 JSON 下载失败 | log.w + 跳过该条，继续下其他字幕 |
| 单条字幕 JSON 格式异常（缺 body） | log.w + 跳过该条 |
| caption_tracks key 冲突 | log.w + 跳过该条（保留先到达的） |

**统一原则：字幕是增量功能，任何失败都不能影响视频本体下载。**

---

## 七、CLI 行为

- **不新增** CLI 参数。复用现有 `--no-caption`（`common.py:1891`）。
- `--no-caption` 已经会跳过 `extractor.py:244-255` 的字幕写盘，所以即使 `caption_tracks` 被填充也不会落盘。
- 但出于效率考虑，`fetch_subtitles` 内部应 **不感知** `--no-caption`（无法跨层访问），即使加了 `--no-caption` 也会调用 SignSrv 和拉字幕 — 这是一个**小浪费**，可接受。如果要优化，可在 `bilibili.py` 调用处 `if not caption: return`，但这意味着把 `caption` 这个 kwargs 从 extractor 主流程传到 prepare，改动面变大，YAGNI 暂不做。

---

## 八、配置

| 环境变量 | 默认值 | 说明 |
|---|---|---|
| `SIGN_SRV_URL` | `http://127.0.0.1:8989` | SignSrv 地址。本地开发场景默认值已可用 |

无其他配置文件，无 CLI 参数。

---

## 九、测试

参照 you-get 项目本身"无 test framework"的现状，本次实现**不引入 unittest 框架**，而是写**1 个手动验证脚本**，放在 `test/manual_test_bili_subtitle.py`：

```bash
# 用法
cd you-get && source venv/bin/activate
# 1. 先启动 SignSrv
cd ../MediaCrawlerPro-SignSrv && venv/bin/python app.py &
cd ../you-get
# 2. 跑测试脚本（需要 cookies）
python test/manual_test_bili_subtitle.py --cookies ~/bili_cookies.txt --bv BV1XXX
```

脚本应能：
- 跑通：打印每条字幕的 lan/type，前 3 行 SRT 内容
- SignSrv 关闭场景：验证 warn 后跳过、视频信息能正常拿
- 无字幕视频场景：验证不报错、log "无可用字幕"

实测校准点（在脚本里都要打印出来供人眼对照）：
- subtitle 列表元素的真实字段名（特别是 AI 判定字段）
- 中文 BV 一例（有 AI 字幕）+ 英文 BV 一例（无字幕）+ 番剧一例

---

## 十、风险与待校准点

1. **AI 判定字段不确定**（spec §4.3）。需在第一次实跑时校准，必要时调整 `is_ai` 判定逻辑。
2. **wbi 签名时效**：SignSrv 内部从 nav 接口取 wbi key 并缓存，B 站可能在风控严的时段拒签或失效。本设计的应对是"签名失败就跳过字幕"，符合 warn skip 策略。
3. **`subtitle_url` 协议前缀**：B 站可能返回 `//xxx` 也可能返回 `https://xxx`，实现时要兼容（已在 §6.2 第 6 步说明）。
4. **cookies 序列化格式**：调 SignSrv 传的 cookies 是 `key=value; key=value` 字符串。need to 确认 `you_get.common.cookies` 的存储格式（CookieJar / dict / str），写一个轻量序列化函数。

---

## 十一、不在本次范围

- 弹幕（已有）
- 给 MediaCrawlerPro-Python 集成字幕（you-get 是独立 CLI）
- 移除 `kuaidaili_proxy.py` 的硬编码兜底（独立问题，已在 `docs/bilibili_no_merge_usage.md` §6 记录）
- 视频本体下载流程改动
