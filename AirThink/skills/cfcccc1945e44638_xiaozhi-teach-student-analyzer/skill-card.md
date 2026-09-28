## Description:

把班级测评成绩转化为知识点弱项分析、学生分层和可执行的教学调整建议。

This skill is ready for commercial/non-commercial use.

## Publisher:

[qizhitang](https://clawhub.ai/user/qizhitang)

### License/Terms of Use:

MIT-0

## Use Case:

面向使用中文的中小学教师：分析班级逐题成绩和历次测评，定位共性弱项，生成班级报告、学生诊断卡和分层教学建议；面向家长的材料须经教师审定。

### Deployment Geography for Use:

Global

## Known Risks and Mitigations:

Risk: Student assessment records could be exposed or shared without permission.

Mitigation: Confirm class-workspace access controls before use, use student aliases, and check consent and privacy controls before parent or cross-skill sharing.

Risk: Small samples or incomplete assessment data could produce misleading student conclusions.

Mitigation: Flag insufficient evidence, omit unsupported trend or item statistics, and have the teacher review conclusions before use.

## Reference(s):

- [ClawHub skill listing](https://clawhub.ai/qizhitang/skills/xiaozhi-teach-student-analyzer)
- [学情分析框架](references/analysis-framework.md)
- [班级学情报告模板](references/class-report-template.md)
- [学生个体诊断卡模板](references/student-diagnosis-card-template.md)

## Skill Output:

**Output Type(s):** [Analysis, Markdown, Guidance]

**Output Format:** [Markdown reports, diagnosis cards, and teaching recommendations]

**Output Parameters:** [1D]

**Other Properties Related to Output:** [Marks insufficient evidence and omits unsupported comparisons; teacher review is required before sharing.]

## Skill Version(s):

2.6.0 (source: release metadata and skill frontmatter)

## Ethical Considerations:

Users should evaluate whether this skill is appropriate for their environment, review any generated or modified files before relying on them, and apply their organization's safety, security, and compliance requirements before deployment.
