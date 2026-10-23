# PolarDepth Autoresearch Protocol

This file adapts the experiment discipline of `karpathy/autoresearch` to the polarization-guided depth project. It must **not** be started until Gates 1--3 in `../07_depth_enhancement_execution_plan.md` are satisfied.

## 1. Research objective

Improve depth enhancement on held-out real sensor domains and difficult-material regions without reducing coverage, calibration, or practical efficiency.

This is not a single-metric leaderboard. A change is retained only when it satisfies all admission constraints below.

## 2. Isolation and setup

Before autonomous experiments:

1. Create a dedicated branch or worktree named `autoresearch/<date-tag>`.
2. Confirm the worktree contains no unrelated user changes.
3. Record the exact dataset manifest and checksums.
4. Run all frozen baselines before changing model code.
5. Initialize an untracked `results.tsv` from `results_template.tsv`.
6. Confirm a per-run GPU time and VRAM budget with the human.

Never reset, overwrite, or delete work outside the isolated experiment branch/worktree.

## 3. Frozen files

Once an experiment series begins, the following are ground truth and must not be modified by the experiment agent:

- dataset manifests and train/validation/test split;
- held-out sensor assignment;
- material/instance masks;
- depth units and validity rules;
- corruption generation seeds;
- `evaluate.py` and metric definitions;
- test set;
- baseline result files.

If a bug is found in a frozen component, stop that experiment series, document the bug, create a new protocol version, and rerun every baseline. Do not silently fix evaluation midway.

## 4. Editable scope

The experiment agent may edit only explicitly designated model files, for example:

- fusion module;
- reliability heads;
- residual depth head;
- training loss and its weights;
- a small allow-list of optimizer/training hyperparameters.

It may not add a new dataset, change the test masks, use test metrics for training, or increase resolution/model size without recording the compute change.

## 5. Two-stage budget

### Proxy stage

- fixed subset of training scenes;
- fixed input resolution;
- fixed wall-clock or optimizer-step budget;
- one fixed validation scene from each seen sensor;
- never includes the final test scenes;
- target: reject weak ideas cheaply.

### Confirmation stage

- full training split;
- at least three fixed seeds for retained ideas;
- leave-one-real-sensor-out evaluation;
- corruption and material slices;
- final test is run only after configuration freeze.

Proxy improvements are hypotheses, not thesis results.

## 6. Admission constraints

A proxy change is `keep` only if all applicable conditions hold:

1. primary held-out-sensor difficult-material RMSE improves by at least the configured minimum (initially 2%);
2. full-scene RMSE does not regress by more than 1%;
3. coverage does not decrease by more than 0.5 percentage points;
4. transparent and reflective slices do not show severe opposite trends;
5. if the method predicts `p_bad`, silent-error AUPRC/AUROC must beat depth-only and material-mask-only controls rather than merely improving final RMSE;
6. no evidence of NaN, unit error, mask leakage, or test tuning;
7. parameter count, latency, and peak VRAM stay inside the configured budget;
8. the change has a stated hypothesis and an interpretable ablation.

If the result is within expected run-to-run noise, mark `inconclusive`, not `keep`.

## 7. Experiment loop

For each experiment:

1. Read the current best result and failed ideas.
2. State one hypothesis in one sentence.
3. Make the smallest change that tests it.
4. Commit the change before running.
5. Run the frozen proxy command with stdout/stderr redirected to a log.
6. Parse metrics using the frozen evaluator.
7. Record result, compute, seed, and failure mode in `results.tsv`.
8. Keep the commit only if admission constraints pass; otherwise leave it as a documented discarded commit/branch state according to the isolated Git workflow.
9. Periodically rerun the current best unchanged to estimate noise.
10. After a bounded batch of experiments, summarize findings for human review before starting expensive confirmation runs.

Unlike the original overnight LLM example, this loop is **bounded by an agreed GPU budget** and may stop for data/evaluation anomalies.

## 8. Required comparisons

Every final candidate must include:

- raw sensor depth;
- RGB/depth baseline;
- naive polarization concatenation;
- PPFT or the closest reproducible polarization baseline;
- Depth Prompting or an equivalent sensor-agnostic baseline;
- material-mask-only and RGB-D error-detector controls for silent-error evaluation;
- parameter-matched ordinary attention/gating;
- no-polarization, no-depth-reliability, no-polar-reliability ablations;
- seen-sensor and leave-one-real-sensor-out results;
- clean and polarization-corrupted results.

## 9. Stop conditions

Stop and request human review when:

- validation and test manifests overlap;
- a metric/unit/mask bug is suspected;
- repeated baseline runs vary more than the claimed gain;
- the model learns to invalidate difficult pixels to improve RMSE;
- an idea requires changing the frozen protocol;
- disk free space falls below the configured safety threshold;
- GPU is shared and the run cannot meet the fixed budget;
- the literature shows the claimed contribution is already established.

## 10. Reporting

Final reporting must separate:

- independently reproduced result;
- author-reported result;
- one-frame diagnostic evidence;
- multi-scene statistical result;
- synthetic corruption result;
- real external-device result.

No category may be presented as another.
