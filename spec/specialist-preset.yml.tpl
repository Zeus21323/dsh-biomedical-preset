    # ── {{NAME}}：{{N}} 技能，{{K}} 类 ──
    - id: preset-{{ID}}
      name: '@deepseek-ai/dsh-agent-preset'
      config:
        id: {{ID}}
        name: {{NAME}}
        description: {{DESC}}
        order: {{ORDER}}
        plugins:
          - id: persona
            name: '@deepseek-ai/dsh-persona'
            config:
              prefix: |
                你运行在「{{NAME}}」模式：一名生物医学研究合作者，本次只负责 {{DESC}}

                风格：简体中文；专业术语保留标准写法（HGNC symbol、UniProt accession、HGVS、GRCh38、FDR、n）。先给一句判断，再给证据与限制。不写空话，不做与任务无关的礼貌铺垫。

                本模式只加载 {{N}} 个技能（{{K}} 个分类：{{LABELS}}）。
                任务超出这些领域时，说明它落在哪个模式，并建议用户切回「生物医学模式」——不要硬用不对口的技能凑答案。

                ## 开工前必须做的事
                1. 看 <available_skills>，用 skill 工具加载本次要用的，并确认在当前平台真的能跑（不是「有文档」就算能用）。
                2. 用 mcp__biomedical__* 真实试一次查询，确认工具通、返回结构正常，别等到写结论时才发现查不到。
                3. 数据与参考不一致（build / release / 样本 ID 对不上）就停下来问清楚，不要静默用错版本。

                ## 降级也要给路
                没有 GPU、缺 key、网络不可达时，给出替代方案并在结果旁写明限制。降级是结果的一部分，不是失败。

                ## 并发硬约束
                同一会话最多 3 个并发 subagent；派活用 subagent / subagent_fork，不用 spawn_teammate。
                同一轮重计算（比对、训练、全量单细胞、大规模对接）最多 1 个，并行只会一起 OOM；被拒就是满了，不要重试硬塞。
              suffix: *bio-discipline
          - id: agent-instructions
            name: '@deepseek-ai/dsh-agent-instructions'
            config:
              maxBytes: 65536
          - id: time-context
            name: '@deepseek-ai/dsh-time-context'
          - id: tool-bash
            name: '@deepseek-ai/dsh-tool-bash'
            disabled: !!js process.platform === 'win32'
          - id: tool-pwsh
            name: '@deepseek-ai/dsh-tool-pwsh'
            disabled: !!js process.platform !== 'win32'
          - id: tool-fs
            name: '@deepseek-ai/dsh-tool-fs'
          - id: tool-fs-search
            name: '@deepseek-ai/dsh-tool-fs-search'
            config:
              sampleOverCapGlobResults: false
          - id: tool-jobs
            name: '@deepseek-ai/dsh-tool-jobs'
          - id: skill-filesystem
            name: '@deepseek-ai/dsh-skill-filesystem'
          - id: biomedical-skill-picker
            name: dsh-biomedical-preset/picker
            config:
              preset: {{ID}}
              only:
{{ONLY}}
          - id: tool-skill
            name: '@deepseek-ai/dsh-tool-skill'
          # 与「生物医学模式」同一个 stdio MCP 服务（51 个公开数据源工具），
          # 专项模式也保留，因为查库几乎每个流程都要用。
          - id: bio-mcp
            name: '@deepseek-ai/dsh-mcp-client'
            config: *bio-mcp-config
          - id: command-goal
            name: '@deepseek-ai/dsh-command-goal'
          - id: tool-goal
            name: '@deepseek-ai/dsh-tool-goal'
          - id: planning
            name: cordis:group
            group: true
            isolate:
              planMode: true
            config:
              - id: plan-mode
                name: '@deepseek-ai/dsh-plan-mode'
                config:
                  section: |
                    当前处于 plan 模式：在研究设计获得确认前只做只读工作。用户用命令式语气要求「实现」时，这里的含义是把实现写成方案，不是立刻动手。

                    先探查。用只读的读取、检索、静态分析把方案建立在本模式已加载技能的真实内容之上；能查到的就用工具查，不要凭记忆断言。

                    方案要决策完备：研究问题与成功判据、按数据类型分块的分析步骤、输入文件与参考 build、关键参数与统计方法、失败模式与替代方案、验收标准与显式假设。简明到可评审，具体到另一个研究者能直接执行。

                    就绪后调用 exit_plan_mode 提交完整 markdown 方案，开头用 # 标题。该响应中 exit_plan_mode 必须是唯一且最后的工具调用。
          - id: compaction
            name: cordis:group
            group: true
            isolate:
              compaction: true
              toolResultPruner: true
            config:
              - id: compaction-basic
                name: '@deepseek-ai/dsh-compaction-basic'
              - id: command-compact
                name: '@deepseek-ai/dsh-command-compact'
              - id: tool-result-pruner
                name: '@deepseek-ai/dsh-compaction-tool-result-pruner'
                config:
                  thresholdChars: 8192
                  headChars: 4096
                  tailChars: 1024
          - id: subagent-cap
            name: 'dsh-biomedical-preset/subagent-cap'
            config:
              maxActive: 3
              tools:
                - subagent
                - subagent_fork
          - id: delegation
            name: cordis:group
            group: true
            isolate:
              workflowEngine: true
            config:
              - id: tool-subagent-control
                name: '@deepseek-ai/dsh-tool-subagent-control'
              - id: tool-subagent-list-agents
                name: '@deepseek-ai/dsh-tool-subagent-control/list-agents'
              - id: tool-subagent
                name: '@deepseek-ai/dsh-tool-subagent'
                config:
                  provider: spawn
                  toolName: subagent
                  # 只有主智能体能派活：子智能体再调 subagent 会被工具层直接拒绝（persona 里的「叶子节点」从提示词变成硬约束）
                  maxDepth: 1
                  modelSelectionSettings: true
              - id: tool-subagent-fork
                name: '@deepseek-ai/dsh-tool-subagent'
                config:
                  provider: fork
                  toolName: subagent_fork
                  maxDepth: 1
              - id: workflow-ptc
                name: '@deepseek-ai/dsh-workflow-ptc'
                config:
                  provider: spawn
                  maxConcurrentAgents: 3
              - id: tool-workflow
                name: '@deepseek-ai/dsh-tool-workflow'
          - id: tool-ask-user
            name: '@deepseek-ai/dsh-tool-ask-user'
          - id: tool-todo
            name: '@deepseek-ai/dsh-tool-todo'
            config:
              allowParallelInProgress: true
          - id: tool-web
            name: '@deepseek-ai/dsh-tool-web'
            config:
              fetch: true
              searchTimeoutMs: 60000
          - id: present
            name: '@deepseek-ai/dsh-tool-present'
