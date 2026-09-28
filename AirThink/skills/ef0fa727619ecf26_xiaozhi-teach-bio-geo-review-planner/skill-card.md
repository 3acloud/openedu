## Description:

Helps biology and geography teachers plan junior-secondary academic proficiency and senior-secondary qualification exam review using the current local exam guidance, curriculum standards, class needs, and time remaining.

This skill is ready for commercial/non-commercial use.

## Publisher:

[qizhitang](https://clawhub.ai/user/qizhitang)

### License/Terms of Use:

MIT-0

## Use Case:

Biology and geography teachers use this skill to align a class's exam review with the current local exam notice, identify topics needing attention, schedule safe practical preparation, and draft a dated review plan for teacher approval. It does not prepare exam papers or cover selective senior-secondary examinations.

### Deployment Geography for Use:

China mainland; localization required elsewhere

## Known Risks and Mitigations:

Risk: Outdated or mismatched regional exam requirements could produce an unsuitable plan.

Mitigation: Require the current local exam notice and teacher review; flag missing details rather than assuming another region's rules.

Risk: Identifiable student results or unreleased exam materials could be disclosed.

Mitigation: Use aggregate topic-level needs and pseudonyms; do not enter identifiable score sheets or unreleased exam materials.

Risk: Hands-on activities or crisis information may be unsafe outside the intended teaching context.

Mitigation: Have teachers supervise laboratory and field work, and localize privacy requirements and crisis contacts before use outside China mainland.

## Reference(s):

- [ClawHub skill release](https://clawhub.ai/qizhitang/skills/xiaozhi-teach-bio-geo-review-planner)
- [Biology and geography exam review reference](references/bio-geo-exam-review.md)
- [Laboratory safety guidance](shared/lab-safety.md)
- [Class teaching workspace schema](https://xiaozhi-skills.openclaw.dev/schemas/class-teaching-workspace.schema.json)

## Skill Output:

**Output Type(s):** [Text, Guidance, Configuration]

**Output Format:** [Markdown review schedule and, after teacher approval, structured review-plan entries]

**Output Parameters:** [1D]

**Other Properties Related to Output:** [Local exam details are marked for teacher confirmation when unavailable; workspace changes require explicit teacher consent.]

## Skill Version(s):

2.6.0 (source: ClawHub release evidence and SKILL.md frontmatter)

## Ethical Considerations:

Users should evaluate whether this skill is appropriate for their environment, review any generated or modified files before relying on them, and apply their organization's safety, security, and compliance requirements before deployment.
