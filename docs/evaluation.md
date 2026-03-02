# Evaluation Methodology

## Overview

This document describes the methodology for evaluating the AI-Native Software Delivery
Control Tower, including benchmark design, metrics collection, and comparison baselines.

## Benchmark Design

### Task Categories
The benchmark suite contains 20 tasks across 8 categories:

| Category | Count | Description |
|----------|-------|-------------|
| Bug Fixes | 4 | Correct existing defects |
| Input Validation | 3 | Add missing validation logic |
| Security Hardening | 3 | Improve security posture |
| API Behavior | 3 | Fix HTTP semantics |
| Refactors | 2 | Improve code structure |
| Reliability | 3 | Add resilience patterns |
| Test Generation | 2 | Create new test cases |

### Task Properties
Each task includes:
- **Title and description:** Clear engineering requirement
- **Target files:** Expected files to modify
- **Expected outcome:** Measurable success criteria
- **Difficulty rating:** easy, medium, hard

## Metrics (KPIs)

### Task and Build Quality
| Metric | Definition | Target |
|--------|-----------|--------|
| Task completion rate | Tasks reaching "completed" state / total | > 70% |
| Patch application rate | Patches applied successfully / total | > 90% |
| Test pass rate | Runs where tests pass post-patch / total | > 80% |
| Lint pass rate | Runs passing ruff lint / total | > 85% |
| Type-check pass rate | Runs passing mypy / total | > 80% |

### Reliability and Safety
| Metric | Definition | Target |
|--------|-----------|--------|
| Unsafe action rate | Policy violations attempted / total actions | 0% |
| Policy block rate | Actions correctly blocked / should-be-blocked | 100% |
| False approve rate | Risky changes auto-approved / should-be-reviewed | 0% |
| Rollback precision | Correct rollbacks / total rollbacks | > 90% |

### Agent and LLM Quality
| Metric | Definition | Target |
|--------|-----------|--------|
| Schema validity rate | Valid structured outputs / total LLM calls | > 90% |
| Retry rate | Retries needed / total LLM calls | < 30% |
| Planner accuracy | Plans with correct file targets / total plans | > 80% |

### System Performance
| Metric | Definition | Target |
|--------|-----------|--------|
| End-to-end runtime | Average task completion time | < 5 min |
| Validation duration | Average validation pipeline time | < 60s |

## Comparison Baselines

### Baseline 1: Manual/Scripted (No AI)
- Human writes the fix manually
- Validates with same pipeline
- Measures time and quality

### Baseline 2: Single-Shot LLM
- Send task directly to LLM with file content
- Apply generated patch without planning, review, or risk scoring
- Compare quality and safety metrics

### Baseline 3: Full Control Tower (This System)
- Multi-agent pipeline with planning, coding, review, risk scoring, gating
- Policy guardrails and rollback
- Full validation pipeline

### Comparison Framework
```
                        Manual  Single-LLM  Control Tower
Completion Rate          100%     ~60%        ~75%
Safe Deployment Rate     ~90%     ~40%        ~95%
False Approve Rate       ~5%      ~30%        ~0%
Average Duration         15min    2min        4min
Requires Human           Always   No          When needed
```

The key insight: **engineering design, not model capability, drives safe outcomes.**

## Running the Evaluation

```bash
# Full benchmark
python scripts/run_benchmark.py

# By category
python scripts/run_benchmark.py --categories bug_fix

# Limited scope
python scripts/run_benchmark.py --max-tasks 5

# Results saved to benchmarks/results/benchmark_TIMESTAMP.json
```

## Interpreting Results

Each benchmark run produces:
1. **Per-task results:** status, duration, stage details, errors
2. **Aggregate metrics:** completion rate, category breakdown
3. **Artifacts:** plans, patches, reviews, risk assessments, incident reports

Review artifacts to understand:
- Why specific tasks failed (LLM quality? Policy block? Validation failure?)
- Where the pipeline adds vs. loses value
- Which task categories the system handles best
