## Description:

A read-only daily dashboard that brings an independent teacher's schedule, student follow-ups, homework, parent communication, and remaining lesson credits into one prioritized view.

This skill is ready for commercial/non-commercial use.

## Publisher:

[qizhitang](https://clawhub.ai/user/qizhitang)

### License/Terms of Use:

MIT-0

## Use Case:

Independent teachers use this skill to review a seven-part daily workspace, identify students needing attention from recorded indicators, and choose three priority actions. It does not change records or send messages.

### Deployment Geography for Use:

Global

## Known Risks and Mitigations:

Risk: Daily summaries may reveal sensitive information about minor students.

Mitigation: Use student aliases, maintain required consent fields, omit sensitive personal details, and have the teacher review any content before sharing.

Risk: Broad daily-planning prompts may invoke the dashboard when it was not intended.

Mitigation: Confirm the teacher wants a workspace summary and limit the response to authorized, read-only records.

Risk: Missing or outdated workspace records may lead to misleading priorities.

Mitigation: Mark unavailable records as missing, ask for the date when needed, and do not present unsupported counts as exact.

## Reference(s):

- [ClawHub skill release](https://clawhub.ai/qizhitang/skills/xiaozhi-teach-solo-dashboard)
- [Daily dashboard template](artifact/references/dashboard-template.md)
- [Seven dashboard block templates](artifact/references/daily-dashboard-block-templates.md)
- [Complete daily dashboard example](artifact/references/daily-dashboard-full-sample.md)
- [Shared teacher workspace schema](artifact/shared/solo-teacher-workspace.schema.json)

## Skill Output:

**Output Type(s):** [Text, Markdown, Guidance]

**Output Format:** [Seven-section Markdown dashboard with a prioritized three-item action list]

**Output Parameters:** [1D]

**Other Properties Related to Output:** [Read-only; student risk flags cite recorded indicators, and follow-up actions require teacher confirmation.]

## Skill Version(s):

2.6.0 (source: ClawHub release and skill frontmatter)

## Ethical Considerations:

Users should evaluate whether this skill is appropriate for their environment, review any generated or modified files before relying on them, and apply their organization's safety, security, and compliance requirements before deployment.
