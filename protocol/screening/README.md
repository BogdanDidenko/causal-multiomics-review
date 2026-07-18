# Screening Contract

The prompt files are canonical runtime artifacts. Schemas define the only
accepted model responses. `gate_config.json` maps criterion values to
deterministic decisions.

Round A runs `scope_reviewer` and `causal_design_reviewer` independently. A
record advances directly only when both gates return `include`. Any `exclude`,
`unclear`, parse failure, or missing required field is sent to adjudication in
the sensitivity-oriented default configuration. The adjudicator returns a
consolidated criterion record; Python then emits `seek_full_text`, `exclude`,
or `manual_review`.

Prompts use `{{RECORD_ID}}`, `{{TITLE}}`, `{{ABSTRACT}}`, `{{YEAR}}`, and
`{{SOURCE}}`. The runner stores prompt/schema hashes and raw responses.

Before screening the full corpus, freeze a human-adjudicated benchmark and
declare acceptance thresholds. The initial prompts are version `0.1.0`, not a
validated production classifier.
