# CLAUDE.md（you-get 项目级指引）

- **版本**: v1.0
- **更新时间**: 2026-05-25

本文件为 Claude Code（claude.ai/code）在本仓库工作时的指引。优先级高于默认行为，低于用户的 `~/.claude/CLAUDE.md` 全局规则。

---

## 一、项目定位

`you-get`（runnerback fork）是 MediaCrawlerPro 套件下的视频下载工具。本 fork 在上游 `soimort/you-get` 基础上增量集成：
- 快代理（默认启用，硬编码兜底有问题待移除）
- Bilibili 音视频分流（复用上游 `-n`）
- Bilibili CC 字幕（含 AI），依赖 `MediaCrawlerPro-SignSrv` 提供 wbi 签名

详情见 `README.md` 与 `docs/` 下文档。

---

## 二、工作流偏好

### 小需求 / 小改动：直接做，不要走 superpowers

**不要默认使用 superpowers**（`brainstorming` / `writing-plans` / 等）。它们对 100 行内的修改、bug fix、文档更新、问答性任务是过度工程，会让简单事变啰嗦。

**判断阈值**：
- ✅ **直接做**：~150 行内代码改动、单文件修改、bug fix、文档/配置改动、回答问题、命令使用、git 操作
- ⚠️ **走完整流程**：多文件协调的大 feature、跨模块重构、需要多方案对比的架构决策，且**用户明确要求或我判断高风险**时

**只有以下情况才用 superpowers**：
1. 用户在消息里**显式**要求（"用 brainstorm"、"先出 spec"、"写 plan"）
2. 任务**确实复杂**（>3 个文件协调 + 影响公共接口 + 决策不可逆）
3. 用户在长对话里反复纠偏，说明思路漂移，需要正式化

不确定时**问一句**："这个量级要走 spec/plan 流程吗，还是直接做？"，不要默认走。

### 编码原则
- 遵守用户全局规则："不要写保底代码,有问题及时暴露,切记!" 
  - 网络/外部服务失败 → log + return None（已是 you-get/SignSrv 的现行风格），但 **不要** 加重试循环、不要静默吞错、不要硬编码兜底凭证
  - `kuaidaili_proxy.py:280-283` 就是反面例子（硬编码 secret_id 兜底，导致"看似连上代理但 IP 被 ban"的误导）
- 中文写文档和 todo
- 文档放 `docs/`，测试放 `tests/`
- 新文档头部加版本号 + 更新时间
- UTF-8 中文

### 测试
- 项目用 stdlib `unittest`，不用 pytest
- 测试文件 `tests/test_*.py`，命令：`venv/bin/python -m unittest discover tests -v`
- 网络/外部服务相关用 `unittest.mock.patch` mock，e2e 验证写独立 `manual_test_*.py` 脚本

### Git
- 不主动操作 git。用户会自己 commit
- 如需要写明 commit 建议，可以写在汇报里，但不要执行

---

## 三、关键文件索引

| 类型 | 文件 | 职责 |
|---|---|---|
| 入口 | `you-get`（脚本）/ `src/you_get/common.py` | CLI 参数解析、下载主流程 |
| Extractor | `src/you_get/extractor.py` | 字幕落盘通用机制（`caption_tracks` → `{title}.{lang}.srt`） |
| Bilibili | `src/you_get/extractors/bilibili.py` | B 站解析（3 处 cid 分支：普通 / 番剧 / festival） |
| Bilibili 字幕 | `src/you_get/extractors/bilibili_subtitle.py` | 本 fork 新增：字幕抓取主流程 + 纯函数 |
| SignSrv 客户端 | `src/you_get/util/signsrv_client.py` | 本 fork 新增：HTTP 调 SignSrv |
| 快代理 | `src/you_get/util/kuaidaili_proxy.py` | 本 fork 新增：含跨进程缓存。⚠️ 有硬编码兜底待移除 |
| 文档 | `docs/bilibili_no_merge_usage.md`, `docs/superpowers/specs/`, `docs/superpowers/plans/` | 已有文档不要无故重写 |

---

## 四、SignSrv 联动注意事项

- 本地默认地址 `http://127.0.0.1:8989`，通过 env `SIGN_SRV_URL` 覆盖
- SignSrv 启动：`cd ../MediaCrawlerPro-SignSrv && venv/bin/python app.py`
- 健康检查：`curl http://127.0.0.1:8989/signsrv/pong`
- 字幕调用：`POST /signsrv/v1/bilibili/sign`，body `{req_data: {...}, cookies: "..."}`

如 SignSrv venv 缺依赖（`xhshow` 等）：`venv/bin/pip install -r requirements.txt` 补装。

---

## 五、常见操作模式

| 用户说 | 做法 |
|---|---|
| "实现 / 加一个 X 功能" | 体量小直接做；体量大或不确定先问 |
| "看一下 / 分析一下 / 是否可以" | 调研类，grep + 读代码 + 简洁汇报，不要走 brainstorm |
| "用一下 / 试一下" | 实测，命令贴出来 |
| "git ..." | 不操作 git，给命令建议 |
| "rebase 冲突" | 按用户规则（"本地" vs "upstream" vs 语义判断）逐个处理，记录到日志 |
