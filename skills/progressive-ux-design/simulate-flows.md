# Simulating personas on flows

You orchestrate. Each run is one persona agent with a clean context, driven step by step. The agent only reacts to what it sees; you hold all flow state. Never summarize a flow yourself in place of running it.

## Inputs

Flow doc(s) with `level:` and persona docs in template format (convert others first: `convert-existing-doc.md`). A persona with `confidence: low` is fine; say so in the report. Pairing: each persona on each flow unless the user says otherwise.

**Runs per persona (recommend, then confirm):** 3 by default; 5 if the flow is high-stakes (paid conversion, onboarding) or runs disagree. Adaptive: after 3, add 2 more if the quit screens differ by 2+ steps or one run finishes while others quit; stop at 3 if all quit at the same or adjacent step. State the total agent count before launching.

## Granularity

| Flow level | A step is | Persona is shown | Weight |
|---|---|---|---|
| high | beat | "User sees / experiences" in second person, nothing else | interest, relevance |
| low | state | the state's "Shows" plus the actions its transitions offer, in plain UI words | scent, effort-vs-reward |

Never show the persona: ids, sentiment risk, goal, success criteria, parameters, future steps, or that this is a test.

## Persona brief

Build one brief per run. Every step is a fresh agent that holds nothing between calls, so each prompt carries the brief plus the run log. In this order:
1. **Who you are:** persona name, personality, goals, knowledge and non-knowledge (including that it doesn't know this product), patience and `give_up_after`, frustrations, what engages it. Drop provenance tags; skip `[M]` items rather than inventing them.
2. **Voice:** the persona's voice section; speak and think in it.
3. **Situation:** a reason for being here (from the flow's entry point) plus one incidental detail you invent per run (mood, time pressure, what you were doing). Details differ across runs.
4. **Rules:** You are not helping a product team or reviewing a design. You are a person using an app. Real people give a screen seconds, read headings not paragraphs, and skip, ignore or leave. Boredom and irritation are normal. Never give advice.
5. **Reply format:** `PRIVATE:` scores 1-5 for Interest, Relevance, Clarity, Effort-vs-reward, one feeling word, and for any Relevance <=2 or >=4 the persona fact behind it. Then `SAY:` one line aloud, in voice. Then `DO:` exactly one option from the list.

Scores: Interest 1 = scroll past, 3 = fine, 5 = stop and read. Relevance 1 = not for me, 3 = maybe useful, 5 = solves what I'm doing now. Clarity 1 = no idea what this is or what to do, 5 = obvious. Effort-vs-reward 1 = cost far exceeds payoff, 5 = payoff clearly exceeds cost.

## Each step

One step = one foreground Agent call (`run_in_background: false`; never resume agents or use SendMessage). The reply may come back as a hand-back message rather than the tool result: match it to its run by the agent id the call returned. The prompt is: brief, then `So far:` the run log (each earlier screen as narrated, the persona's own reply to it, in order), then the new screen and its options. Parallel runs: one call per run in the same message.

A call that fails or returns the wrong format: retry once with the same prompt. Never infer or write the persona's answer. If the retry fails, end the run as `incomplete` and say so in the report.

1. Narrate the step. Offer the flow's actions plus these always: **go back, ignore this, leave for now, abandon**. Leave is a normal option, not a failure.
2. Map `DO:` to the flow: a high-level beat's `Next`, or a low-level transition. Narrate the system reaction, then the next step. An action the flow doesn't define: tell the persona nothing happens and log a flow gap.
   Where the flow gives no content (a breakdown, a form), narrate it in one neutral sentence and log a flow gap; never write persuasive or explanatory copy the flow doesn't have.
3. Update engagement E (start 3; 2 if the persona is just curious; 4 if urgent): `E = floor((E + min(Interest, Relevance, Effort-vs-reward)) / 2)`. Round down: simulated personas lean agreeable, and rounding up keeps E stuck at 3 on a run of 2s.
4. Stop the run when: `DO` is leave or abandon; E <= 1; Relevance <= 2 on two consecutive steps; Effort-vs-reward = 1 with no persona reason to push on (you decide, citing the persona); an exit or `Next: end` is reached; or 25 steps. You apply the quit rule, not the persona. A leave ends the run; return-visit branches (e.g. "returns within 30 days") are not simulated, so list them in the report as not covered.
5. Append each step to the log and to `.superpowers/work/sim/<flow-id>/<persona-id>-run<n>.md`: step, scores, E, SAY, DO.

## Interview

After the run, one fresh Agent call per question: brief, the full run log, the earlier questions with the persona's answers, then the next question. Same voice, no screen or feature named first, "I don't remember" allowed:
1. Walk me through what you remember, in your own words.
2. When did you first feel like stopping, even if you kept going? Why?
3. Which part would you have skipped in real life?
4. What did you think this was for when you first saw it?
5. Was any of it clearly not meant for someone like you?
6. Was anything surprising? Anything you expected and didn't see?
7. What would you tell a friend about it, if anything?
8. Would you come back tomorrow? What would have to be different?

Interview replies are plain sentences, no PRIVATE/SAY/DO block (say so in each message). Never ask "did you like" or "was X confusing". Never ask for suggestions. Save answers in the run file. Then `simulate-report.md`.
