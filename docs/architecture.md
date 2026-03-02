# Architecture Documentation

## System Architecture

The AI-Native Software Delivery Control Tower is organized into six architectural layers, each with clear responsibilities.

## Layer 1: Ingestion Layer

**Responsibility:** Accept and parse engineering tasks, scan repositories, load policies.

### Components:
- **Task Parser:** Receives engineering task descriptions via API
- **Repo Scanner:** Extracts repository metadata (language, file tree, key modules)
- **Policy Loader:** Loads and validates YAML-based policy configurations

### Design Decisions:
- Tasks are stored in SQLite for persistence and auditability
- Repository scanning uses ripgrep for fast code search with grep fallback
- Policy loading fails safely — if parsing fails, the system blocks all actions

## Layer 2: Agent Orchestration Layer

**Responsibility:** Coordinate LLM-powered and rule-based agents through the pipeline.

### Agents:
1. **Planner Agent (LLM)** — Transforms task + repo context → implementation plan
2. **Code Agent (LLM)** — Generates code patches from plan + file contents
3. **Reviewer Agent (LLM)** — Evaluates patch correctness and alignment
4. **Security Agent (Rule-based)** — Normalizes Bandit/pip-audit findings
5. **Release Agent (Rule-based)** — Determines deployment gate strategy
6. **Incident Agent (Rule-based)** — Processes canary anomalies

### Design Decisions:
- LLM agents use structured JSON output validated against Pydantic schemas
- All LLM calls include automatic retry with fallback model
- Security, Release, and Incident agents are deliberately rule-based for reliability
- Each agent output is stored as an artifact for auditability

## Layer 3: Tool Execution Layer

**Responsibility:** Execute external tools and manage codebase operations.

### Tools:
- **LLM Client:** Ollama API wrapper with structured output, retries, JSON extraction
- **Git Ops:** Branch creation, commit, reset, diff management
- **Patch Applicator:** File modification with blocked-path enforcement
- **Validation Pipeline:** pytest, ruff, mypy, bandit, pip-audit runners
- **Deploy Simulator:** Canary deployment with synthetic metrics

### Design Decisions:
- Git operations use CLI directly (not GitPython) for transparency
- Validation tools run as subprocesses with timeout protection
- Each validation result is normalized into a common schema
- Deployment simulator generates realistic synthetic metrics for the MVP

## Layer 4: Decision Layer

**Responsibility:** Compute risk, enforce policies, and make deployment decisions.

### Components:
- **Risk Engine:** Weighted scoring with configurable factors and thresholds
- **Policy Engine:** YAML-based rules for safety constraints
- **Gate Decision Logic:** Maps risk + validation status → deployment action

### Design Decisions:
- Risk scoring is fully explainable — every factor shows its weight and penalty
- Policy ambiguity always resolves to the stricter interpretation
- Gate decisions can be: approve, canary, human_review, or block
- The system never auto-approves when uncertain

## Layer 5: Observability and Reliability Layer

**Responsibility:** Monitor canary deployments and manage rollbacks.

### Components:
- **Canary Metric Comparison:** Baseline vs. candidate metrics
- **Regression Detection:** Threshold-based with consecutive breach counting
- **Rollback Trigger:** Automatic rollback on policy-defined breaches
- **Incident Reporter:** Anomaly summary + postmortem draft

### Design Decisions:
- Threshold-based detection is used for MVP (not ML anomaly detection)
- Consecutive breach counting prevents false alarms from single spikes
- Rollback is automatic when thresholds are breached
- Every incident generates a postmortem draft artifact

## Layer 6: Persistence and Artifacts Layer

**Responsibility:** Store all run data, artifacts, and traces for auditability.

### Components:
- **SQLite Database:** Tasks, runs, run states, agent outputs, validations, risk assessments, deployments, incidents, artifacts
- **Artifact Manager:** Filesystem storage for patches, reports, prompts, LLM outputs

### Design Decisions:
- SQLite with WAL mode for concurrent read/write access
- All artifacts stored on filesystem with metadata tracked in SQLite
- Prompts and raw LLM outputs stored for debugging and evaluation
- Run state transitions logged for timeline reconstruction

## State Machine

The run lifecycle follows a validated state machine:

```
PENDING → PLANNING → CODING → VALIDATING → REVIEWING
  ↓         ↓          ↓          ↓          ↓
FAILED    FAILED    FAILED/    FAILED     FAILED
                    BLOCKED
                    
REVIEWING → RISK_SCORING → GATING → DEPLOYING → MONITORING
                            ↓           ↓           ↓
                         BLOCKED    COMPLETED   ROLLING_BACK
                         HUMAN_REV              → COMPLETED
                         COMPLETED
```

Invalid transitions are rejected to maintain pipeline integrity.

## Data Flow

```
Task → Planner(LLM) → Plan
Plan → Coder(LLM)   → Patch
Patch → Git Apply   → Modified Repo
Modified Repo → Validation Pipeline → Report
Report + Patch → Reviewer(LLM) → Review
Report + Review → Risk Engine → Risk Score
Risk Score + Policy → Release Agent → Gate Decision
Gate Decision → Canary Simulator → Metrics
Metrics → Incident Agent → Rollback or Complete
```

## Security Model

1. **Blocked Paths:** Policy prevents modifications to sensitive files
2. **File Count Limits:** Maximum 5 files per autonomous change
3. **Patch Size Limits:** Maximum 500 lines per change
4. **Human Approval:** Required for auth/security/database changes
5. **Structured Outputs:** All LLM outputs validated before use
6. **Fail-Safe Defaults:** Block on uncertainty
