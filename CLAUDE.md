# CLAUDE.md（you-get 项目级指引）

- **版本**: v2.0
- **更新时间**: 2026-05-25

本文件为 Claude Code 在本仓库工作时的指引。优先级低于 `~/.claude/CLAUDE.md` 全局规则，高于默认行为。

---

## 一、项目定位

**you-get（runnerback fork）** = 视频/音频/弹幕/字幕下载工具。fork 自上游 [soimort/you-get](https://github.com/soimort/you-get)。

**纯下载职责**：不维护账号池、不维护代理池、不实现签名算法 — 这些都从外部 HTTP 服务拉取（见下方架构图）。

## 二、在 MediaCrawlerPro 体系中的位置

```
┌────────────────┐  签名         ┌────────────────┐
│ you-get        │ ─────────────►│ SignSrv :8989  │
│ (本项目)       │               └────────────────┘
│                │  cookies/proxy ┌─────────────────────────┐
│                │ ──────────────►│ MediaCrawlerPro-Python  │
│                │                │ 资源服务 :8990          │
└────────────────┘                └─────────────────────────┘
```

零配置启动流程：
1. `cookies` 自动从资源服务 `GET /api/v1/bili/cookies` 拉
2. 字幕签名自动从 SignSrv `POST /signsrv/v1/bilibili/sign` 拉
3. 代理自动从资源服务 `GET /api/v1/proxy/kuaidaili` 拉

任一环节失败 → log.w 后降级或跳过 → 不阻塞视频本体下载。

## 三、关键命令

```bash
source venv/bin/activate

# 默认行为（自动拉 cookies + 自动用代理 + 自动签字幕）
./you-get https://www.bilibili.com/video/BVxxxxxx

# 音视频分流（不合并）
./you-get -n https://www.bilibili.com/video/BVxxxxxx

# 显式禁用资源服务代理
./you-get --disable-srv-proxy https://www.bilibili.com/video/BVxxxxxx

# 显式提供 cookies（覆盖资源服务）
./you-get --cookies ~/bili_cookies.txt https://www.bilibili.com/video/BVxxxxxx

# 单元测试
venv/bin/python -m unittest discover tests -v
```

## 四、文档索引

| 文档 | 用途 |
|---|---|
| `README.md` | 项目总览：架构、增量能力、命令、配置、依赖 |
| `docs/bilibili-no-merge.md` | B 站音视频分流下载（`-n` 用法详解 + 产物结构） |
| `.env.example` | 环境变量模板（`SIGN_SRV_URL`、`RESOURCE_SRV_URL`） |

## 五、关键文件

```
src/you_get/util/
    signsrv_client.py          # 调 SignSrv 拿 wbi 签名
    cookies_srv_client.py      # 调资源服务拿 cookies
    proxy_srv_client.py        # 调资源服务拿代理 URL
src/you_get/extractors/
    bilibili.py                # B 站解析（上游）+ 3 处调字幕模块
    bilibili_subtitle.py       # 字幕抓取主流程（本 fork 新增）
tests/
    test_signsrv_client.py     # SignSrv 客户端单测
    test_bilibili_subtitle.py  # 字幕纯函数单测
    manual_test_bili_subtitle.py  # e2e 验证脚本
```

## 六、工作流偏好

- **不操作 git** — 用户自己 commit
- **不主动用 superpowers** — 小改动直接做
- **不写保底代码** — 服务不可达 / 凭证缺失 → log.w + 跳过，**不**写硬编码默认值兜底
- **新文档命名** kebab-case，加版本号 + 更新时间

## 七、不在本项目范围

- 签名算法 → `MediaCrawlerPro-SignSrv`
- cookies / 代理管理 → `MediaCrawlerPro-Python` 资源服务
- 视频元数据爬取 / 入库 → `MediaCrawlerPro-Python` CLI 爬虫
