#!/usr/bin/env python3
"""validate.py — agent-permission-gate Agent 权限策略七维校验器

输入: Agent 权限接入计划 JSON（schema 见 tests/sample_good.json）
  {
    "scope": {
      "touches_real_repo": true,          // Agent 是否碰真实代码库
      "touches_secrets": true,            // 是否碰真实密钥
      "worth_deploy": true                // 决策点：是否值得上运行时拦截
    },
    "sandbox": {
      "empty_verified": true,             // 空沙箱三步已验证（status/Connected/Authenticated/create）
      "small_project_trio": true          // 三件事已验：工具能跑/网络规则够/被拒不混淆
    },
    "policy": {
      "read_dirs": ["<repo>/src"],        // 读目录白名单（非空）
      "write_dirs": ["<repo>/src"],       // 写目录白名单（非空）
      "domains": ["registry.npmjs.org"],  // 域名白名单（非空）
      "file_mode": "hard_requirement",    // hard_requirement | best_effort
      "no_wildcards": true,               // 无通配主机/宽地址段
      "grained_rule": true                // 规则粒度=程序+主机+端口
    },
    "credentials": {
      "all_via_provider": true,           // 密钥全走 Provider 占位令牌
      "none_in_env_files_prompts": true,  // 密钥未出现在环境变量/文件/提示词
      "leaked_keys_rotated": true,        // 出现过真值的旧密钥已轮换
      "endpoint_declared": true           // 每个凭据声明了端点（联网≠带密钥）
    },
    "approval": {
      "auto_approve": false,              // 自动批准（观察期内必须 false）
      "policy_advisor_auto": false,       // Agent 自提案自动生效（必须 false）
      "observation_period_done": true,    // 人工审批观察周期已跑满
      "observation_log_exists": true      // 权限观察日志存在
    },
    "discipline": {
      "output_is_draft": true,            // Agent 输出当草稿（审查/测试/版本管理照常）
      "k8s_networkpolicy_tested": false   // 上 K8s 前 deny-all 测试过插件执行
    }
  }

七维校验（任一 FAIL → exit 1）：
  D1 决策点一致: touches_real_repo 或 touches_secrets 为 true 时 worth_deploy 必须 true
     （碰真实仓库/密钥却不上拦截 = 裸奔）；两者皆 false 时 worth_deploy 必须 false
     （小脚本配保险箱 = 收益不抵学习成本）
  D2 空沙箱先行: worth_deploy=true 时 empty_verified 且 small_project_trio 必须 true
     （别一上来接真实仓库）
  D3 策略先行: worth_deploy=true 时 read_dirs/write_dirs/domains 均非空且
     no_wildcards=true 且 grained_rule=true（三张白名单+无通配+细粒度）
  D4 文件模式: worth_deploy=true 时 file_mode 必须为 hard_requirement
     （best_effort = 静默放行陷阱，你以为锁着其实没锁）
  D5 密钥零落地: touches_secrets=true 时 all_via_provider、none_in_env_files_prompts、
     leaked_keys_rotated、endpoint_declared 必须全 true
     （能联网≠能带密钥；出现过即泄露）
  D6 审批纪律: auto_approve=false 且 policy_advisor_auto=false；
     observation_period_done=true 时 observation_log_exists 必须 true
     （无日志=没观察，画像没底）
  D7 边界纪律: output_is_draft=true（沙箱管越权不管写错）；
     若声明上 K8s（k8s_networkpolicy_tested 出现在 true 语义的上下文中），
     必须 deny-all 测试过——此处简化：k8s_networkpolicy_tested=true 时
     要求 observation_period_done=true（先个人跑通再团队/K8s）

退出码：0=通过 / 1=有缺陷 / 2=文件/格式错误
"""
import json
import sys


def fail(checks, code, msg):
    checks.append(("FAIL", code, msg))


def ok(checks, code, msg):
    checks.append(("OK", code, msg))


def validate(plan):
    checks = []
    sc = plan.get("scope") or {}
    real = sc.get("touches_real_repo") is True
    secrets = sc.get("touches_secrets") is True
    worth = sc.get("worth_deploy") is True

    # D1 决策点一致
    if (real or secrets) and not worth:
        fail(checks, "D1", f"碰真实仓库/密钥（repo={real}, secrets={secrets}）却 worth_deploy=false——裸奔进真实仓库")
    elif not (real or secrets) and worth:
        fail(checks, "D1", "只写独立小脚本却 worth_deploy=true——收益不抵学习成本")
    else:
        ok(checks, "D1", f"决策点一致（repo={real}, secrets={secrets} → deploy={worth}）")

    # D2 空沙箱先行
    if worth:
        sb = plan.get("sandbox") or {}
        if sb.get("empty_verified") is not True or sb.get("small_project_trio") is not True:
            fail(checks, "D2", "空沙箱验证未完成（empty_verified/small_project_trio）——别一上来接真实仓库")
        else:
            ok(checks, "D2", "空沙箱三步+三件事已验证")
    else:
        ok(checks, "D2", "不上拦截，空沙箱豁免")

    # D3 策略先行
    if worth:
        p = plan.get("policy") or {}
        missing = [k for k in ("read_dirs", "write_dirs", "domains")
                   if not p.get(k)]
        if missing:
            fail(checks, "D3", f"白名单缺失: {missing}——接真实仓库前必须三张白名单齐全")
        elif p.get("no_wildcards") is not True:
            fail(checks, "D3", "no_wildcards=false——通配主机/宽地址段是危险口子，规则须限定到程序+主机+端口")
        elif p.get("grained_rule") is not True:
            fail(checks, "D3", "grained_rule=false——规则粒度须到 程序+主机+端口")
        else:
            ok(checks, "D3", "三张白名单齐全且无通配细粒度")
    else:
        ok(checks, "D3", "不上拦截，策略先行豁免")

    # D4 文件模式
    if worth:
        mode = (plan.get("policy") or {}).get("file_mode")
        if mode != "hard_requirement":
            fail(checks, "D4", f"file_mode={mode!r}——best_effort 是静默放行陷阱，规则失效时沙箱照样跑，必须 hard_requirement")
        else:
            ok(checks, "D4", "文件策略 hard_requirement")
    else:
        ok(checks, "D4", "不上拦截，文件模式豁免")

    # D5 密钥零落地
    if secrets:
        c = plan.get("credentials") or {}
        bad = [k for k in ("all_via_provider", "none_in_env_files_prompts",
                           "leaked_keys_rotated", "endpoint_declared") if c.get(k) is not True]
        if bad:
            fail(checks, "D5", f"密钥纪律缺: {bad}——密钥零落地：Provider 占位令牌/不进环境文件提示词/泄露即轮换/端点声明（联网≠带密钥）")
        else:
            ok(checks, "D5", "密钥零落地四纪律齐全")
    else:
        ok(checks, "D5", "不碰密钥，D5 豁免")

    # D6 审批纪律
    ap = plan.get("approval") or {}
    if ap.get("auto_approve") is not False:
        fail(checks, "D6", "auto_approve=true——观察期内禁止自动批准")
    elif ap.get("policy_advisor_auto") is not False:
        fail(checks, "D6", "policy_advisor_auto=true——Agent 自提案自放行=裁决者与被裁决者合一")
    else:
        if ap.get("observation_period_done") is True and ap.get("observation_log_exists") is not True:
            fail(checks, "D6", "观察周期已跑满但无观察日志——没记录=没观察，权限画像没底")
        else:
            ok(checks, "D6", "审批纪律通过（人工审批+Advisor 关闭"
               + ("+日志在" if ap.get("observation_log_exists") else "") + "）")

    # D7 边界纪律
    d = plan.get("discipline") or {}
    if d.get("output_is_draft") is not True:
        fail(checks, "D7", "output_is_draft=false——沙箱管越权不管写错，审查/测试/版本管理照常做")
    else:
        if d.get("k8s_networkpolicy_tested") is True and ap.get("observation_period_done") is not True:
            fail(checks, "D7", "上 K8s 但观察周期未跑满——先个人跑通有权限画像，再团队/K8s")
        else:
            ok(checks, "D7", "边界纪律通过（输出当草稿"
               + ("+K8s 前置顺序合规" if d.get("k8s_networkpolicy_tested") is True else "") + "）")

    return checks


def main():
    if len(sys.argv) != 2:
        print("usage: python validate.py policy.json", file=sys.stderr)
        return 2
    try:
        with open(sys.argv[1], encoding="utf-8") as f:
            plan = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print(f"ERROR: 无法读取/解析: {e}", file=sys.stderr)
        return 2
    if not isinstance(plan, dict):
        print("ERROR: 顶层必须是 JSON 对象", file=sys.stderr)
        return 2

    checks = validate(plan)
    fails = [c for c in checks if c[0] == "FAIL"]
    for status, code, msg in checks:
        if status == "FAIL":
            print(f"[{code}] FAIL {msg}")
    print(f"== {len(checks) - len(fails)} OK / {len(fails)} FAIL ==")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
