## Description:

为中国大陆初高中化学教师生成以宏观现象、微观粒子和化学符号为主线的教案草稿，支持初中单元整合和高中必修衔接课。

This skill is ready for commercial/non-commercial use.

## Publisher:

[qizhitang](https://clawhub.ai/user/qizhitang)

### License/Terms of Use:

MIT-0

## Use Case:

面向中国大陆初高中化学教师，根据班级课时、薄弱点和学生分层拟定化学教案、提问链、单元整合方案与初高衔接课；所有输出须由教师审核后使用。

### Deployment Geography for Use:

中国大陆；在其他地区部署前须本地化危机求助渠道。

## Known Risks and Mitigations:

Risk: AI 生成的教案或题目可能含有不准确的化学概念或题目。

Mitigation: 教师核对教案，并在课堂使用或入库前验算生成的题目。

Risk: 实验位可能被误认为可直接执行的操作方案。

Mitigation: 只规划实验目标和观察点并标注安全等级；器材、操作和安全流程交由专门的实验指导，并由教师按学校条件复核。

Risk: 班级资料可能包含学生的个人敏感信息。

Mitigation: 仅使用班级、化名或座号，不在教案中写入真实姓名、联系方式、家庭或健康信息。

## Reference(s):

- [化学课程主题与初高衔接对照](references/chemistry-curriculum-map.md)
- [实验安全约定](shared/lab-safety.md)
- [AI 出题自检协议](shared/ai-item-check.md)
- [班级教学工作空间数据结构](shared/class-teaching-workspace.schema.json)
- [危机转介协议](shared/crisis-referral-protocol.md)
- [ClawHub 技能页面](https://clawhub.ai/qizhitang/skills/xiaozhi-teach-chemistry-lesson-planner)

## Skill Output:

**Output Type(s):** [Text, Markdown, Guidance]

**Output Format:** [中文 Markdown 教案草稿与提问链]

**Output Parameters:** [1D]

**Other Properties Related to Output:** [按班级课时和学情调整；实验位标注安全等级；教师确认后方可使用或保存。]

## Skill Version(s):

2.6.0 (source: ClawHub release evidence and skill frontmatter)

## Ethical Considerations:

Users should evaluate whether this skill is appropriate for their environment, review any generated or modified files before relying on them, and apply their organization's safety, security, and compliance requirements before deployment.
