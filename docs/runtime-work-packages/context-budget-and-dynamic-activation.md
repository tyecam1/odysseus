# Context budget and dynamic activation

## Objective

Assemble the smallest sufficient agent context for each request by selecting memory, skills, tools and documents under an explicit budget.

## Scope

- classify prompt components as mandatory, conditional or excluded;
- record byte/token contribution by component;
- load tools and skills by task type and permission profile;
- retain the user request and active objective near the actionable end of context;
- expose fallback reasons when a requested capability is omitted;
- test 4k, 8k, 16k and larger context profiles.

## Acceptance criteria

- smaller-context models complete representative tasks without losing required authority instructions;
- irrelevant tools, memories and skills are measurably reduced;
- prompt-injection tests from documents, memories and skills remain blocked;
- no domain memory or source root is loaded outside the deployment policy;
- the change includes unit tests and actual runtime measurements.

## Non-goals

No new memory authority, no global skill catalogue, no silent summarisation of source evidence and no permission widening.
