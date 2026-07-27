# Session focus and uncertainty closeout

## Objective

Keep one active objective during a run and end substantive sessions with reliable continuation state.

## Behaviour

- load objective, permitted actions and stop condition at start;
- maintain an adjacent-idea parking lot;
- detect repeated replanning, scope expansion and unsupported completion;
- ask at closeout: “What are you least confident about?” and “What is the biggest thing I may be missing about the situation right now?”;
- classify answers as uncertainty, assumption, missing context, dependency or speculative opportunity;
- never turn the answers into new work without a separate task-creation action.

## Acceptance criteria

Works across interactive agents, scheduled jobs and handoffs; trivial sessions may omit the full closeout; unchanged uncertainty deduplicates; completion cannot be reported without verification evidence.
