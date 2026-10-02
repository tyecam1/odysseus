# Secret-scan allowlist (gitleaks)

`.gitleaks.toml` keeps the **default gitleaks ruleset fully on** (`useDefault = true`) and adds exactly one exception.

## What it allows, and why

Before the exception, `gitleaks git` reported 69 findings on every pull request, all rule `generic-api-key`, all in a
single historical commit (`ddb5ec37`, "LM2: quantisation-aware family screening + finalist sweep"), all in
`evals/local_models/results/artifacts/`, all the JSON field `model_key`. A permanently red scan trains reviewers to ignore
it, which is the opposite of what a secret scan is for.

Each of the 69 was checked, not assumed: the `model_key` value in every one is a plain model identifier and equals the
name of the directory the artifact is filed under. There are three distinct values:

- `gemma4-12b-qat-gguf-direct`
- `gemma4-26b-a4b-qat-gguf-direct`
- `gemma4-e4b-qat-gguf-direct`

The exception applies only when **all** of these hold (`condition = "AND"`): the rule is `generic-api-key`, the commit
is `ddb5ec37f55a21a802a938a4cdfef4e286a06607`, the path is that LM2 artifact tree, and the matched text is exactly
`model_key": "<one of the three values>"`. A new file, a different commit, any other value or any other rule is scanned
exactly as before.

## How to re-verify

```text
gitleaks git --no-banner --redact .                          # with .gitleaks.toml: no leaks found

# the default ruleset alone (no exception): the 69 findings return
printf '[extend]
useDefault = true
' > /tmp/default-only.toml
gitleaks git --no-banner --redact --config /tmp/default-only.toml .
```

The exception was also tested negatively in a throwaway repository: a planted GitHub-style token is still reported
(`github-pat`), and a `model_key` line in the allowed path but in a different commit is still reported
(`generic-api-key`).

Note: `--config /dev/null` is **not** a way to see the findings; an empty config loads no rules at all and reports nothing.

## Rules for changing it

Do not widen it to a rule-wide or path-wide ignore. If a new benchmark artifact legitimately trips the rule, prefer
making the artifact not look like a credential (for example a different field name) over adding an allowlist entry.
