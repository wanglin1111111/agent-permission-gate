# agent-permission-gate

Agent 权限治理与运行时硬拦截技能（OpenShell 方法论）：规则从提示词软要求变成执行时硬拦截——以前只能"求"Agent 别乱来，现在能"强制"它别乱来。

一句话：**Agent 决定做什么，OpenShell 决定能做到哪一步。**

## 架构底座

- 问题：权限靠信任——提示词里的规矩没有执行力
- 网络：裁决权在沙箱外 Supervisor，Agent 没资格自证安全
- 文件：Landlock 限制目录读写；⚠️ 默认 best_effort 静默放行，必须改 hard_requirement
- 密钥：Provider 托管真凭据，Agent 只拿占位令牌；能联网 ≠ 能带密钥（credential_endpoint_mismatch）
- 补权限：拒绝→提案→人批准，热加载；Policy Advisor 默认关闭
- 校验：Policy Prover（SMT）验证策略本身，不验证 Agent 代码
- 边界：管越权不管写错；管权限不管云推理内容外发

## 解决什么

| 痛点 | 本技能的做法 |
|---|---|
| Agent 碰真实代码库/密钥，权限只能"求" | 运行时硬拦截：工具落地那一刻卡住 |
| 不知道值不值得上 | 决策点：碰真实仓库+密钥→半天跑通；小脚本→收益不抵成本 |
| 一上来接真实仓库出事 | 空沙箱验证三步 + 无敏感数据项目验三件事 |
| 事后补策略 | 最小权限三张白名单先行（读/写目录 + 域名） |
| 以为锁着其实没锁 | 文件策略必须 hard_requirement（best_effort = 静默放行陷阱） |
| 密钥进环境变量/文件/提示词 | 全走 Provider 占位令牌；出现过即视为泄露 → 轮换 |
| 被拒请求不会判读 | 事件 Playbook：程序+目的地+凭据上下文判读流程 |
| 团队各搞一套 | 策略模板沉淀（文件白名单+域名白名单+Provider 凭据），K8s 前先验 NetworkPolicy 执行 |

## 安装

复制本目录到 `~/.agents/skills/`（或你的 Skill 加载路径）即可。

## 自检

```bash
python scripts/validate.py tests/sample_good.json   # 必须 exit 0
python scripts/validate.py tests/sample_bad.json    # 必须 exit 1

# 一行自验（正反向 + 退出码全覆盖，零依赖）
python tests/test_validate.py
```

## 结构

```
SKILL.md                              工作流入口（一条主线 + 6 步流程 + 7 条硬规则 + 边界）
references/architecture.md            架构原理（沙箱外裁决/Landlock/Provider 占位令牌/Policy Prover/边界）
references/onboarding-playbook.md     落地六步实操（空沙箱清单/三张白名单模板/Provider 配置/观察周期/团队推广）
references/incident-playbook.md       事件 Playbook（被拒判读/静默放行告警/密钥轮换/策略模板格式/K8s 前置）
references/gotchas.md                 10 个坑位（best_effort 陷阱/通配/自动批准/沙箱当代码质量工具/TLS 盲区…）
scripts/validate.py                   Agent 权限策略七维校验器（exit 0/1/2）
tests/sample_good.json                通过基准
tests/sample_bad.json                 拦截基准(裸奔/空沙箱缺/白名单缺/ best_effort/密钥落地/自动批准…)
docs/methodology.md                   方法论全文（奥卡姆剃刀提炼 + 8 条核心 + 6 步行动指南）
```
