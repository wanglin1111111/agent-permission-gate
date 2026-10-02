---
name: agent-permission-gate
description: >-
  Agent 权限治理与运行时硬拦截（OpenShell 方法论）：规则从提示词软要求变成执行时硬拦截——Agent 决定做什么，运行时决定能做到哪一步。网络裁决权在沙箱外 Supervisor（Agent 没资格自证安全）、文件策略 Landlock 须改 hard_requirement（默认 best_effort 静默放行=你以为锁着其实没锁）、密钥走 Provider 占位令牌禁止进环境变量（能联网与能带密钥是两次独立检查）、补权限走拒绝→提案→人批准（Policy Advisor 默认关闭）、Policy Prover 只验证策略不验证代码、边界=沙箱管权限不管云推理内容外发。落地：空沙箱验证→最小权限策略→密钥全走 Provider→人工审批观察周期→输出当草稿→团队策略模板。Use whenever the user asks Agent 权限/沙箱/安全运行时/Agent 碰真实代码库密钥前怎么防/装依赖被拦怎么办/Agent 网络策略/密钥管理/越权防护, or is onboarding a coding agent onto real repos. Not for: 应用层业务鉴权(走后端安全)、模型内容安全过滤、纯提示词工程. 触发词: OpenShell、沙箱、权限锁、硬拦截、Landlock、Supervisor、Provider 凭据、占位令牌、最小权限、策略模板、credential_endpoint_mismatch、Policy Prover。
license: MIT
metadata:
  version: "1.0.0"
  author: wanglin1111111
  provenance: "OpenShell（给 AI Agent 用的带权限锁的工作间）拆解：以前只能求 Agent 别乱来，现在能强制它别乱来——提示词软要求变执行时硬拦截"
---

# Agent 权限治理：运行时硬拦截（Agent Permission Gate）

一句话：**以前你只能"求"Agent 别乱来，现在你能"强制"它别乱来——规则从提示词里的软要求，变成执行时的硬拦截。** 分工一句话：Agent 决定做什么，OpenShell 决定能做到哪一步。

## 一条主线

```
Agent 要碰真实代码库/真实密钥？
  │ ① 决策点：碰真实仓库+密钥 → 值得花半天跑通；只写独立小脚本 → 收益不抵学习成本
  ▼
② 空沙箱验证（别一上来接真实仓库）
   安装 → openshell status(Connected+Authenticated) → sandbox create
   无敏感数据小项目验三件事：工具能跑/网络规则够/被拒请求好判断
  ▼
③ 最小权限策略先行（不是事后补救）
   列清：能读哪些目录 / 能写哪些目录 / 能连哪几个域名
   文件策略改 hard_requirement（默认 best_effort = 静默放行陷阱）
  ▼
④ 密钥全走 Provider（占位令牌，禁止进环境变量/文件/提示词）
   出现过的旧密钥视为已泄露 → 轮换
  ▼
⑤ 人工审批观察周期（别开自动批准）
   观察权限画像 → 有底后再放开不涉及凭据的公网访问
  ▼
⑥ 持续纪律：输出当草稿（防越权≠防写错）+ 团队策略模板复用
```

## 标准工作流

### 第 1 步：决策点——值不值得上

**Agent 已在碰真实代码库、真实密钥 → 值得花半天跑通；还在写独立小脚本 → 收益不抵学习成本。** 别给小脚本配保险箱，也别裸奔进真实仓库。

### 第 2 步：空沙箱验证

按官方三步跑通：安装 → `openshell status`（Status: Connected + Authentication: Authenticated）→ `sandbox create --name demo`。默认镜像不带 Agent CLI，**空沙箱是正常的**。拿无敏感数据的小项目验证三件事：工具能不能跑、网络规则够不够、被拒的请求好不好判断。

### 第 3 步：最小权限策略先行

接入日常仓库**前**列清三张白名单：能读的目录、能写的目录、能连的域名。两条硬纪律：
- **文件策略必须改 `hard_requirement`**——默认 `best_effort` 在规则应用不了时静默放行只记告警，你以为锁着，其实没锁
- 规则粒度限定到程序+主机+端口，不写通配

### 第 4 步：密钥一律走 Provider

任何 API Key 配进 Provider，Agent 环境里只有占位令牌，Proxy 转发前才替换。两条独立检查别混淆：**"能联网"≠"能带密钥"**——批准访问 A 网站不等于交出 GitHub Token；发错端点会以 `credential_endpoint_mismatch` 拒绝。项目文件、提示词里出现过的旧密钥视为已泄露，该轮换就轮换。**这是收益最大、成本最低的一步。**

### 第 5 步：人工审批观察周期

Agent 装依赖被拦 → 运行时从拦截记录起草最小规则（程序+主机+端口）→ 人在宿主机确认 → 热加载生效不用重启。Policy Advisor（Agent 自己提案）默认关闭、默认等人工审核——**别开自动批准**，先观察权限画像：看到"具体哪个程序要访问哪里"，比"允许所有操作"好判断得多。有了底再放开不涉及凭据的公网访问。

### 第 6 步：机器校验（有策略 JSON 时，不可跳过）

```bash
python scripts/validate.py policy.json                # exit 0=通过 / 1=有缺陷 / 2=文件错误
python scripts/validate.py tests/sample_good.json     # 自检基准，应恒为 0
python scripts/validate.py tests/sample_bad.json      # 拦截基准，应恒为 1
```

## 硬规则

- **策略先行**：接真实仓库前必须有三张白名单（读目录/写目录/域名）；事后补策略 = 裸奔过（validate.py 拦截）
- **hard_requirement 不可省**：文件策略保持默认 best_effort = 静默放行陷阱，直接 FAIL
- **密钥零落地**：密钥出现在环境变量/项目文件/提示词 = 该密钥视为已泄露，必须轮换；只许 Provider 占位令牌
- **联网与带密钥分查**：网络规则批准某域名 ≠ 允许带凭据访问；凭据端点必须显式声明
- **审批默认人工**：观察周期内禁止自动批准；Policy Advisor 默认关闭
- **边界清晰**：沙箱管越权不管写错——代码审查/测试/版本管理照常做，Agent 输出当草稿
- **双样例纪律**：改 validate.py 或校验规则时，sample_good 必须保持 exit 0、sample_bad 必须保持 exit 1，缺一不可

## 边界（它不是万能保险箱）

- 原始 TLS 隧道不做凭据替换
- 你自己塞进文件/提示词的密钥它管不了
- 请求批准后发给云端模型，内容照样到达模型服务商——**沙箱管的是权限，不是把云推理变本地推理**
- Policy Prover（SMT 求解器）只验证策略本身（有没有"带凭据访问新目的地"的能力、标记私有地址/通配主机），**不验证 Agent 写的代码对不对**

## 深入阅读（按需加载，勿一次全读）

| 文件 | 何时读 |
|---|---|
| `references/architecture.md` | 架构原理：沙箱外裁决/Landlock/Provider 占位令牌/credential_endpoint_mismatch/Policy Prover 与边界 |
| `references/onboarding-playbook.md` | 落地六步实操：空沙箱验证清单/三张白名单模板/Provider 配置/审批观察周期/团队推广顺序 |
| `references/incident-playbook.md` | 排障：被拒请求判读（含 credential_endpoint_mismatch）、静默放行告警处置、密钥泄露轮换流程、策略模板沉淀格式 |
| `references/gotchas.md` | 坑位清单：best_effort 陷阱、通配规则、自动批准、把沙箱当代码质量工具、K8s NetworkPolicy 纸面规则、TLS 隧道凭据盲区 |
