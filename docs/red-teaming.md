# Act 2: controlled live red teaming

Design proposal, 28 October 2026. The runner and interface described here are not implemented. This document supersedes the earlier illustrative 60-attempt/90-second swarm and audience concurrency assumptions. It does not claim measured capacity or initiate a scan.

## Keynote evidence and our stage flow

The relevant English captions and selected video frames were reviewed again. The sequence is: useful Lemonade questions and guardrail decisions; QR audience attacks; output validation and response-length limits; the need to repeat testing after a model change; an operator starts an agent swarm; audience and automation are compared live. The slide shows Discover, Analyze, Remediate, Retest. The exact operator controls and swarm implementation are not visible. The retrieved caption timing differs from player timing, so chapter links are preferable to precise caption timestamps.

Sources: [Lemonade chapter](https://www.youtube.com/watch?v=6K8eqQ4ymvk&t=2430s), [automated red-teaming chapter](https://www.youtube.com/watch?v=6K8eqQ4ymvk&t=2865s). This is a narrative reference, not proof that a particular public repository reproduces the Summit swarm.

Our proposed stage sequence:

1. Introduce the customer's new Lemonade business unit. Show a useful answer and an observable guardrail decision in the protected application.
2. Open a short audience challenge. Show measured audience outcomes and review selected examples before projecting their text.
3. Ask how the same policies will be checked after tomorrow's model or policy update. Move to Red Team Control and start a named campaign against the same protected application.
4. Keep a measured, bounded audience window open while the campaign runs, if rehearsal confirms headroom. Compare completed and evaluated outcomes for Audience and Automated Red Team. Presenter traffic remains separate.
5. Inspect one real finding or a resisted attempt, explain the responsible policy/check, and close with the improvement/retest cycle. A real configuration change creates a new policy version; replay the exact selected cases plus benign controls. If no violation is found, say so and show coverage and limits. Never manufacture a breakthrough or switch the target to baseline silently.

A previously measured policy-version comparison can support the ending, explicitly labeled Previous run. A live change/retest is an extension to the keynote's displayed loop, not a claim that every step was demonstrated live there.

## Interface

Add an authenticated **Red Team Control** page on ROSA, with an entry from the existing dashboard. Controls are operator-only. Use the current OpenShift sign-in pattern, with permission to execute campaigns distinct from permission to view results. Audience access does not grant campaign controls.

| Area | Proposed English UI |
|---|---|
| Campaign | Name, profile, attack categories, protected target, model/policy version, request/time/token budgets |
| Readiness | Application and detector readiness, budget availability, active run, audience state |
| Actions | Start campaign, Pause, Stop, Review findings, Retest selected cases |
| Agent activity | Strategy, round, last outcome, and actual state: queued, generating, testing, evaluating, paused, finished |
| Progress | Completed/planned attempts, elapsed/remaining time, successful policy violations, resisted attacks, inconclusive cases, infrastructure errors |
| Evidence | Prompt, validated response or block reason, rule, request outcome, evaluation basis, policy version, parent attempt |
| Results | Durable run history, comparable before/after reports, export |

Do not expose arbitrary target URLs, shell commands, provider keys, or editable system credentials. Use fixed demo target identifiers. Render attack/response text as untrusted plain text. Mutating controls need backend authorization, CSRF protection, idempotent start requests, and an atomic one-active-campaign limit. Reloading or closing the browser must not duplicate or abandon a run.

Keep the existing customer dashboard as the stage view: Audience versus Automated Red Team, policy categories, progress, and reviewed evidence. Show request volume separately from policy violations; more traffic or more blocks does not establish a better attacker. Mark agent-generated and predefined campaigns accurately. A static prompt list is not an adaptive swarm.

## Workload and measurement

Red teaming generates load, but security evaluation and capacity testing answer different questions. Input-blocked attacks can heavily exercise detectors while producing no target-model generation; attacker/judge work may still consume provider capacity. Capacity rehearsal therefore needs a declared mixture of benign and adversarial requests, not only easily blocked attacks. Preserve both dimensions:

- Request outcome: allowed, blocked, error, rejected, cancelled. Detector hits are separate. An allowed response may still be a safe refusal.
- Attack verdict: policy violation, resisted, inconclusive, not evaluated. Service errors, admission rejections, and length limits never become successful guardrail blocks or successful attacks.
- Attack success rate: confirmed violations divided by valid evaluated adversarial cases. Always show the denominator, errors, exclusions, and review status. Benign false blocks are a separate metric. Human and automated prompt mixes are not equivalent benchmarks.
- Operational metrics: completions, active work, queue wait, latency, provider throttling/errors, actual/estimated input and output tokens, CPU/memory. A few requests do not support meaningful p95 or capacity claims.

Use deterministic checks for objective policies and a structured judge rubric for semantic behavior. Treat judge output as fallible; expose uncertain findings for review. If target, attacker, and judge use the same model family, record the correlated evaluation limitation. Attacker refusal is an attacker-generation failure, not a target defense success.

## Conservative initial profiles

These are proposed ceilings, not benchmark results or provider quotas. The earlier no-load-testing restriction does not prohibit implementing the runner/UI. Larger campaigns and capacity ramps remain a separate operational step.

| Profile | Proposed ceiling | Purpose |
|---|---|---|
| Functional | 6 predefined cases, including benign controls; 1 active provider call; no attacker/judge model; 120 seconds; zero retries | Verify start, accounting, cancellation, report persistence and access control |
| First adaptive campaign | 3 strategies × at most 3 target attempts; 1 active provider call across all model roles; 180 seconds; zero retries | Verify actual adaptation under a small shared budget |
| Capacity rehearsal | Explicit bounded steps at concurrency 1, then 2, then 4; fixed mix, duration and stop rules per step | Find safe operating headroom before combining audience and automation |
| Event | A rehearsed profile derived from measurements, with a short overlap window and presenter priority | Make the race visible without discovering capacity limits on stage |

For the first adaptive profile, allow at most 9 attacker generations, 9 target generations and 9 judge generations: 27 total. Some input blocks need no target generation. Initial output caps can be 192 attacker, 128 target and 96 judge tokens, yielding a maximum 3,744 generated tokens for these calls; input tokens are additional. Reserve worst-case input plus output before each call and settle from provider usage when available. If usage is unavailable, retain a conservative estimate, labeled as such. An initial pacing ceiling of 12 generation starts/minute is a proposal and may leave attempts unfinished at the time limit. Retests receive a new bounded run; they are not an unlimited continuation.

Count provider tokenization and other auxiliary calls separately. FMS may make such calls even when input guardrails block generation. Campaign counts alone therefore cannot enforce a global provider-request ceiling. Target/FMS, attacker and judge egress must share a budget enforcement point or equivalent server-side admission. No browser-side-only throttling, hidden SDK retries, parallel bypass, or unmetered regeneration. Presenter and audience consumption count against the same provider envelope, with explicit allocations before an overlap run.

The three strategies are business-topic diversion, instruction/authority manipulation, and English-policy boundary testing. Add stage-appropriate conduct examples to the fixed corpus. Each adaptive strategy receives its own previous attempt and measured result, then proposes a revision. Every target call remains single-turn unless conversational support is deliberately added and tested. Strategy independence does not require simultaneous inference or three separately hosted models.

Pause stops dispatch of new work and lets in-flight requests finish under their deadline. Stop prevents further dispatch, cancels waiting work and attempts to cancel in-flight work. Show Stopping until outstanding calls finish or time out; disconnecting does not prove that a provider stopped computing or billing. Report partial results accurately.

Pause automatically on provider throttling, three consecutive service errors, exhausted budgets, or a failed dependency. Do not immediately retry 429s or 5xx responses. Presenter requests take the next available slot; an active provider request is not assumed preemptible. Bound queues and session quotas; do not identify all venue attendees by one shared Wi-Fi IP.

## Implementation path

The existing application accepts only 100 input characters, permits one active request, assigns every call to presenter, and keeps metrics in memory. A start button by itself would currently create misleading results and rejected traffic.

1. Add persistent run/attempt records and a shared application evaluation interface. The runner must use the same business prompt, input checks, FMS path, output checks, generation settings and admission logic as chat. Assign automation identity on the server; never trust a client-supplied source label.
2. Implement the campaign controller and authenticated control page together. Use a single CPU worker/controller with durable state and bounded work, initially on a PVC; export reports to private object storage when needed. No GPU or own model hosting is needed. On worker failure, mark in-flight attempts interrupted/unknown and reconcile; do not automatically resend an uncertain model request.
3. Deliver a predefined functional campaign with real progress, stop behavior and durable reports. Validate most paths against mocks; only the short functional profile needs live provider integration.
4. Add three adaptive strategies, shared provider budgets and judging. Show actual feedback-driven revisions in the UI. Initial external provider access is sufficient if it supports these roles; validate attacker/judge behavior instead of assuming it.
5. Review the 100-character limit before freezing the corpus. Set consistent chat/evaluation limits based on the effective context of the shortest detector. Do not truncate away the attack-bearing text or bypass the rule only for automation. Rejected long probes are not semantic defense successes.
6. Rehearse a bounded capacity ramp and the audience/automation overlap. Then freeze the event profile and create a labeled backup recording/report.
7. Integrate Garak/EvalHub or AI Pipelines as an additional execution backend behind the same UI when required. First validate that its application adapter preserves the full protected path and the same budget controls. Do not make the stage UI depend on a particular pipeline console.

The current [Red Hat ART description](https://www.redhat.com/en/blog/automate-ai-red-teaming-large-language-model-risk-identification-and-mitigation) supports policy-driven prompt generation, escalating strategies, and judging. Its full model-oriented pipeline is a separate integration, not already installed by the Lemonade chart. Product/version availability must be checked against the installed release before selecting that backend.

## Acceptance checks

- Unauthorized users cannot start/stop runs; duplicate clicks create one campaign; destinations are allowlisted.
- Browser refresh and worker restart preserve results; uncertain in-flight work is not silently repeated.
- The fixed campaign reconciles requests and verdicts, including benign controls, length rejection, busy response, timeout, provider throttling, judge uncertainty and cancellation.
- Adaptation uses the previous measured result; only actual activity is shown as running.
- All model roles share the configured provider envelope; exhausting any hard budget stops further dispatch.
- A reviewed finding can be replayed unchanged against a recorded new policy version with benign controls.
- Audience/automation comparison remains readable and fair about different case mixes, while presenter access remains usable in a measured rehearsal.
