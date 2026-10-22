# hermes-plugin-ccfddl

[Hermes Agent](https://github.com/NousResearch/hermes-agent) 插件：查计算机领域学术会议（CCF 推荐会议等）的投稿截止时间。

- 按**会议简称**（CVPR、ACL、NeurIPS……）或**领域**（人工智能、数据库、网络、安全、软件工程……）查，也能只看 CCF-A / B / C
- 各会议的 AoE / UTC±N / 太平洋时间统一换算成**北京时间**，附剩余时间（不到一天按小时算）
- 返回排好版的文本，agent 原样转发就行；只读，不需要任何 key

数据来自社区维护的 [ccfddl/ccf-deadlines](https://github.com/ccfddl/ccf-deadlines)。

## 输出样例

问"人工智能的会议 ddl 有哪些"：

```
人工智能会议 DDL（北京时间）：
1. EuroGP 2027 [CCF-None] - 2026-11-02 19:59（剩余 10 天）
2. EvoApplications 2027 [CCF-None] - 2026-11-02 19:59（剩余 10 天）
3. EvoCOP 2027 [CCF-None] - 2026-11-02 19:59（剩余 10 天）
4. EvoMUSART 2027 [CCF-None] - 2026-11-02 19:59（剩余 10 天）
5. CVPR 2027 [CCF-A] - 2026-11-17 19:59（剩余 25 天）
……
```

问"CVPR 什么时候截稿"（单个会议会多给摘要截止、会期地点和官网）：

```
会议 DDL（北京时间）：
1. CVPR 2027 [CCF-A] - 2026-11-17 19:59（剩余 25 天）
CVPR 2027：IEEE/CVF Conference on Computer Vision and Pattern Recognition
  摘要截止：2026-11-11 19:59
  会期/地点：June 20-25, 2027 Seattle, WA, United States
  官网：https://cvpr.thecvf.com/Conferences/2027
```

问"最近能投哪些 A 会"（不限领域，按截止时间排）：

```
近期会议 DDL（北京时间）：
1. WWW 2027 [CCF-A] - 2026-10-26 19:59（剩余 3 天）
2. VLDB 2027 [CCF-A] - 2026-11-02 09:00（剩余 10 天）
3. STOC 2027 [CCF-A] - 2026-11-03 19:59（剩余 11 天）
```

（以上为 2026-10-22 生成；截止时间以会议官网为准。）

## 安装

```bash
hermes plugins install InvolutionHell/hermes-plugin-ccfddl --enable
```

或者手动：

```bash
git clone https://github.com/InvolutionHell/hermes-plugin-ccfddl ~/.hermes/plugins/ccfddl
hermes plugins enable ccfddl
```

`enable` 会通知正在运行的 gateway 现场加载插件，**不用重启**。

依赖：YAML 解析用 Hermes 自带的 `ruamel.yaml`，没有的话退回 `PyYAML`。

## 让 agent 用上

工具名 `conference_deadlines`，所在工具集 `ccfddl`。

- 如果某个平台在 `config.yaml` 里写了显式的工具集列表，把 `ccfddl` 加进去，例如：

  ```yaml
  platform_toolsets:
    telegram: [web, clarify, ccfddl]
  ```

- 插件工具可能是延迟加载的（模型先 `tool_search` 再调用）。工具描述里已经有"会议 / 截稿 / DDL"等关键词，一般能搜到；想更稳，可以在该平台的提示词里加一句"问会议截稿时间就用 conference_deadlines，结果原样发"。

## 参数

| 参数 | 说明 |
|---|---|
| `query` | 会议简称（`CVPR`）、领域（`人工智能` / `AI` / `数据库` / `网络` / `安全` / `软件工程`……）；留空 = 所有领域里最近截止的 |
| `ccf_rank` | 可选，`A` / `B` / `C`（也接受 `CCF-A`） |

领域对应 CCF 推荐目录的十个方向：人工智能、计算机图形学与多媒体、计算机科学理论、数据库/数据挖掘/内容检索、计算机体系结构/并行与分布计算/存储系统、人机交互与普适计算、交叉/综合/新兴、计算机网络、网络与信息安全、软件工程/系统软件/程序设计语言。

## 实现说明

- 数据：`https://ccfddl.com/conference/allconf.yml`，进程内缓存 6 小时，另存一份到 `$HERMES_HOME/cache/ccfddl/allconf.yml`，拉取失败时用这份旧的。
- 每个会议取所有年份、所有轮次里**还没截止的最早一个**；标为 `TBD` 的跳过。
- 一次最多列 30 条，多出的提示缩小范围。

## 开发

```bash
pip install pytest ruamel.yaml   # 或 PyYAML
pytest
```

测试只覆盖纯函数（时区换算、匹配、排版），不联网。

## 致谢与许可

- 会议数据：[ccfddl/ccf-deadlines](https://github.com/ccfddl/ccf-deadlines)，MIT License，Copyright (c) 2021 CCFDDL。本插件只在运行时读取其公开发布的汇总文件，不随仓库分发数据。
- 本插件：MIT License，见 [LICENSE](LICENSE)。
