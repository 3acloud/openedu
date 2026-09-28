## Description:

帮助独立教师生成周课表、检查排课冲突，并管理请假、补课、调课与课时包台账。

This skill is ready for commercial/non-commercial use.

## Publisher:

[qizhitang](https://clawhub.ai/user/qizhitang)

### License/Terms of Use:

MIT-0

## Use Case:

独立教师使用此技能根据学员可上课时间安排课程、发现教师或学员时间冲突，并查询课时包剩余数量与到期日。请假、补课和调课建议经教师确认后才写入课表；课后扣课时、收费和家长沟通不在此技能范围内。

### Deployment Geography for Use:

中国大陆；在其他地区使用前需本地化语言、紧急求助信息、课程假设及未成年人数据规则。

## Known Risks and Mitigations:

Risk: 未确认的排课或调课可能覆盖现有安排，或与学员可上课时间冲突。

Mitigation: 检查教师及学员的可用时间，取得教师确认后再写入课表；补课还需学员或家长确认。

Risk: 课表和课时记录可能暴露未成年人的个人信息。

Mitigation: 使用学员化名和必要的时间信息；敏感信息默认不收集，建档与跨技能共享前核对同意状态。

Risk: 中国大陆的紧急求助、课程和未成年人数据规则在其他地区可能不适用。

Mitigation: 在其他地区部署前本地化相关指引与规则，不直接沿用中国大陆的求助号码。

## Reference(s):

- [ClawHub 技能页面](https://clawhub.ai/qizhitang/skills/xiaozhi-teach-schedule-manager)
- [周课表与课时台账模板](references/weekly-schedule-template.md)
- [请假、补课与调课登记模板](references/leave-makeup-reschedule-forms.md)

## Skill Output:

**Output Type(s):** [Text, Markdown]

**Output Format:** [中文文本和 Markdown 表格]

**Output Parameters:** [1D]

**Other Properties Related to Output:** [生成周课表、冲突检查和课时台账；经教师确认后可更新课表与课时包记录。]

## Skill Version(s):

2.6.0 (source: ClawHub release metadata and SKILL.md frontmatter)

## Ethical Considerations:

Users should evaluate whether this skill is appropriate for their environment, review any generated or modified files before relying on them, and apply their organization's safety, security, and compliance requirements before deployment.
