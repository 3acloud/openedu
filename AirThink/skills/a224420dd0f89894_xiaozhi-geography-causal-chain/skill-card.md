## Description:

引导初高中学生逐步连接地理现象的起因、中间过程和结果，练习完整的因果分析。

This skill is ready for commercial/non-commercial use.

## Publisher:

[qizhitang](https://clawhub.ai/user/qizhitang)

### License/Terms of Use:

MIT-0

## Use Case:

面向中国课程体系的初高中学生，帮助他们通过逐步提问理解地球运动、气候、地形与河流、板块运动及人地关系的成因，并练习原因类题目。

### Deployment Geography for Use:

中国大陆课程场景；其他地区使用前须核对课程内容、未成年人数据要求和当地求助渠道。

## Known Risks and Mitigations:

Risk: 未成年人学习档案和跨技能共享可能暴露个人学习信息。

Mitigation: 默认仅使用当前会话；仅在明确同意后启用档案、共享或提醒，并提供查看、更正、导出、暂停和删除入口。

Risk: 中国课程内容和危机求助渠道可能不适用于其他地区。

Mitigation: 部署前核对当地课程、未成年人数据要求与求助渠道；未确认地区时不把中国大陆号码作为通用联系方式。

## Reference(s):

- [ClawHub 技能页面](https://clawhub.ai/qizhitang/skills/xiaozhi-geography-causal-chain)
- [地理成因链参考指南](references/causal-chain-guide.md)
- [地理错因维度表](shared/geography-error-dimension-table.md)
- [学习档案数据规范](https://xiaozhi-skills.openclaw.dev/schemas/dna-profile.schema.json)

## Skill Output:

**Output Type(s):** [Text, Guidance]

**Output Format:** [对话文本，可包含逐步提问、文字成因链和练习反馈]

**Output Parameters:** [1D]

**Other Properties Related to Output:** [默认仅在当前会话内辅导；学习档案、跨技能共享、错题交接和提醒需分别取得同意。]

## Skill Version(s):

2.6.0 (source: release evidence and skill frontmatter)

## Ethical Considerations:

Users should evaluate whether this skill is appropriate for their environment, review any generated or modified files before relying on them, and apply their organization's safety, security, and compliance requirements before deployment.
