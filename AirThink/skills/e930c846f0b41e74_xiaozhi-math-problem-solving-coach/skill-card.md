## Description:

面向初中至高一学生的数学解题教练，通过追问和逐级提示帮助学生理解单题、订正错误、练习同类题并在明确提出时梳理考点。

This skill is ready for commercial/non-commercial use.

## Publisher:

[qizhitang](https://clawhub.ai/user/qizhitang)

### License/Terms of Use:

MIT-0

## Use Case:

Chinese-speaking middle-school and first-year high-school students use this skill to work through a math problem with guided questions, check mistakes, practice a similar problem, or review for an imminent exam. Profile access, record handoff, and reminders require the student's explicit consent in the current session.

### Deployment Geography for Use:

China (mainland); localize curriculum, crisis contacts, and minor-consent rules before use elsewhere

## Known Risks and Mitigations:

Risk: A minor's learning records or answers could be shared beyond the current session without their understanding.

Mitigation: Review consent settings and obtain explicit current-session permission before profile reads, wrong-answer handoffs, reminders, or parent and cross-skill sharing.

Risk: Crisis contacts, curriculum, and minor-consent rules may not fit learners outside the intended Chinese K12 setting.

Mitigation: Localize these elements before deployment elsewhere; confirm the learner's region before giving crisis contact details.

## Reference(s):

- [ClawHub skill release](https://clawhub.ai/qizhitang/skills/xiaozhi-math-problem-solving-coach)
- [Four-step tutoring workflow](artifact/references/photo-4step-statemachine.md)
- [Math coaching and Socratic questions](artifact/references/math-socrates-guide.md)
- [Hint ladder](artifact/shared/hint-ladder.md)
- [AI-generated question checks](artifact/shared/ai-item-check.md)
- [Crisis exception and localization](artifact/shared/crisis-exception.md)

## Skill Output:

**Output Type(s):** [Text, Guidance, Practice questions]

**Output Format:** [Conversational text with worked steps or markdown when helpful]

**Output Parameters:** [1D]

**Other Properties Related to Output:** [Optional consent-gated wrong-answer handoff; no default profile read, archiving, or reminders.]

## Skill Version(s):

2.6.0 (source: ClawHub release metadata and skill frontmatter)

## Ethical Considerations:

Users should evaluate whether this skill is appropriate for their environment, review any generated or modified files before relying on them, and apply their organization's safety, security, and compliance requirements before deployment.
