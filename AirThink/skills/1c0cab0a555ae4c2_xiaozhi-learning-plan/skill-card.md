## Description:

Creates practical study plans for Chinese K–12 students, with weekly plans for upper-primary students and 30-day plans for older students, and helps adjust them as work progresses.

This skill is ready for commercial/non-commercial use.

## Publisher:

[qizhitang](https://clawhub.ai/user/qizhitang)

### License/Terms of Use:

MIT-0

## Use Case:

Students and their families use this skill to schedule specific study tasks around available time, learning needs, and upcoming exams. With separate consent, it can use a learning-profile summary, prepare a parent-facing task board, or queue reminders through a companion skill.

### Deployment Geography for Use:

Mainland China (simplified-Chinese K–12 context); localize curriculum, guardian consent, reminders, and crisis resources before use elsewhere.

## Known Risks and Mitigations:

Risk: A minor's study information or progress could be shared without appropriate consent.

Mitigation: Require distinct opt-ins before reading a learning-profile summary, generating a parent-facing board, or queuing reminders; honor student refusal and applicable guardian-consent requirements.

Risk: Mainland-China curriculum, consent defaults, reminder behavior, or crisis contacts may be inappropriate elsewhere.

Mitigation: Localize these assumptions before deployment outside mainland China, and confirm the student's region before providing crisis contacts.

## Reference(s):

- [ClawHub skill listing](https://clawhub.ai/qizhitang/skills/xiaozhi-learning-plan)
- [Study plan templates](references/plan-templates.md)
- [Grade-band guidance](shared/grade-bands.md)
- [Consent and reminder conventions](shared/vocab.md)
- [Crisis referral guidance](shared/crisis-referral-protocol.md)

## Skill Output:

**Output Type(s):** [Text, Markdown, Guidance]

**Output Format:** [Chinese-language study schedules, progress summaries, and optional parent-facing boards in text or Markdown]

**Output Parameters:** [1D]

**Other Properties Related to Output:** [Profile access, parent sharing, and reminder handoff require separate opt-in; planning remains available without them.]

## Skill Version(s):

2.6.0 (source: ClawHub release metadata and skill frontmatter)

## Ethical Considerations:

Users should evaluate whether this skill is appropriate for their environment, review any generated or modified files before relying on them, and apply their organization's safety, security, and compliance requirements before deployment.
