# 遗留系统接管助手 — 使用手册

## 简介

`legacy-scan` 是一个命令行工具，扫描任意 Git 仓库，自动生成**系统接管手册**，包含：

- 📄 系统说明书（模块结构、技术栈概览）
- 🏗️ 架构图（Mermaid 组件图）
- 🗄️ 数据库 ER 图（表格、字段、关系）
- 🔗 上下游依赖关系图
- ⚠️ 风险评估报告（安全漏洞、技术债、单点故障、bus factor 等）

一句话：**接盘侠的救星。**

---

## 安装

```bash
cd /home/hermes/.hermes/projects/legacy-takeover
uv pip install -e .
```

安装后 `legacy-scan` 命令全局可用。

---

## 快速开始

### 1. 扫描一个远程仓库

```bash
legacy-scan https://github.com/org/repo
```

默认深度 `standard`，输出到当前目录。

### 2. 指定扫描深度

```bash
# 快速扫描（只做结构和依赖，约 30 秒）
legacy-scan https://github.com/org/repo --depth quick

# 标准扫描（结构 + 依赖 + DB + 风险，约 2 分钟）
legacy-scan https://github.com/org/repo --depth standard

# 深度扫描（全部分析 + AST + 安全审计，约 5 分钟）
legacy-scan https://github.com/org/repo --depth deep
```

### 3. 指定输出目录

```bash
legacy-scan https://github.com/org/repo -o /tmp/my-reports
```

### 4. 只分析不生成报告

```bash
legacy-scan https://github.com/org/repo --no-report
```

终端直接看结果，不写文件。

### 5. 扫描本地仓库

```bash
legacy-scan /path/to/local/repo --depth deep
```

---

## 输出文件结构

扫描完成后，会在输出目录下生成：

```
legacy-report/{仓库名}-20260610-143022/
├── index.html              ← 🌐 浏览器打开，交互式仪表盘
├── SYSTEM_MANUAL.md        ← 📄 系统接管总览
├── ARCHITECTURE.md         ← 🏗️ 架构图 + 模块列表
├── DATABASE.md             ← 🗄️ 数据库 ER 图 + 表详情
├── DEPENDENCIES.md         ← 🔗 依赖关系图
├── RISK_REPORT.md          ← ⚠️ 风险矩阵（按严重度排序）
├── diagrams/
│   ├── architecture.mmd    ← Mermaid 源码（可二次编辑）
│   ├── er_diagram.mmd
│   └── dependency_graph.mmd
└── data/
    ├── modules.json         ← 结构化数据（供程序消费）
    ├── dependencies.json
    └── risks.json
```

**推荐用法** ：先打开 `index.html` 看交互式仪表盘，再读 `SYSTEM_MANUAL.md` 了解全局。

---

## Hermes Skill 模式（对话触发）

在微信聊天中直接对 Hermes 说：

> 分析一下 https://github.com/foo/bar

或者：

> 给我生成这个项目的架构文档

Hermes 会自动调用本工具，把报告摘要贴给你，并在本地保存完整报告。

---

## 支持的语言

| 语言 | 检测特征 | 特有风险检查 |
|------|----------|-------------|
| **Python** | `*.py`, `requirements.txt`, `pyproject.toml` | 硬编码密钥、TODO 密度、缺失测试 |
| **Java** | `*.java`, `pom.xml`, `build.gradle` | `Thread.sleep()`、TODO 密度 |
| **Go** | `*.go`, `go.mod` | 硬编码密钥、缺失错误处理 |
| **TypeScript** | `*.ts`, `*.tsx`, `package.json` | 硬编码密钥、过度 console.log |
| **C#** | `*.cs`, `*.csproj`, `*.sln` | 硬编码密钥、`Thread.Sleep()` |
| **C** | `*.c`, `*.h`, `Makefile` | `strcpy()` 缓冲区溢出、`malloc` 无 `free` |
| **C++** | `*.cpp`, `*.hpp`, `CMakeLists.txt` | `new` 无 `delete`、`reinterpret_cast` |

混合语言仓库（比如 Python + TypeScript 单体）会被同时识别，各自输出结果。

---

## 自定义风险规则

在目标仓库根目录创建 `.legacy-takeover.yaml`：

```yaml
custom_rules:
  - pattern: "Thread\\.sleep"
    file_glob: "*.java"
    category: performance
    severity: 4          # 2=INFO 4=LOW 6=MEDIUM 8=HIGH 10=CRITICAL
    message: "避免使用 Thread.sleep()"
    recommendation: "改用异步调度器"

  - pattern: "console\\.log"
    file_glob: "*.ts"
    category: tech_debt
    severity: 2
    message: "清理调试日志"

  - pattern: "eval\\("
    file_glob: "*.js"
    category: security
    severity: 8
    message: "eval() 有代码注入风险"
    recommendation: "避免使用 eval"
```

工具扫描时会自动加载该文件，把自定义规则匹配到的结果合并到风险报告中。

---

## 风险评分说明

每个风险由两项指标计算：

```
风险分数 = 严重度 (1-10) × 置信度 (0-1)
```

| 严重度 | 含义 | 例子 |
|--------|------|------|
| 🔴 CRITICAL (10) | 必须立即处理 | 生产环境密钥硬编码 |
| 🟠 HIGH (8) | 高优先级 | 无测试覆盖、strcpy 溢出 |
| 🟡 MEDIUM (6) | 应该修复 | Thread.sleep 在请求路径 |
| 🟢 LOW (4) | 低优先级 | 少量 TODO 标记 |
| 🔵 INFO (2) | 参考信息 | console.log 残留 |

---

## 常见问题

**Q: 扫描大仓库很慢怎么办？**

A: 先用 `--depth quick` 快速看概览，需要深入再看具体模块。`quick` 模式只做结构和依赖分析，不解析 AST。

**Q: 能扫描私有仓库吗？**

A: 需要本机 `git` 有访问权限。支持 HTTPS（会弹密码）和 SSH（需要配置好 key）。

**Q: 怎么添加新语言支持？**

A: 实现一个 `LanguageAnalyzer` 子类（约 200 行），注册到 `pyproject.toml` 的 `entry_points` 即可。不改任何核心代码。

---

## 项目文件结构

```
legacy-takeover/
├── pyproject.toml              ← 包配置 + 插件注册
├── src/legacy_takeover/
│   ├── cli.py                  ← CLI 入口
│   ├── core/
│   │   ├── engine.py           ← 核心流水线
│   │   ├── git.py              ← 仓库克隆
│   │   ├── detector.py         ← 语言检测
│   │   └── aggregator.py       ← 结果聚合
│   ├── plugins/
│   │   ├── base.py             ← 插件接口 + 数据模型
│   │   ├── {python,java,go,typescript,csharp,c,cpp}.py
│   ├── risk/
│   │   ├── engine.py           ← 风险引擎
│   │   └── loader.py           ← YAML 规则加载
│   └── report/
│       ├── renderer.py          ← 报告渲染
│       └── templates/           ← Jinja2 模板
└── tests/                       ← 86 个测试用例
```
