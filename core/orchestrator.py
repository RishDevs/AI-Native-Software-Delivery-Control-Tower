"""Pipeline orchestrator — coordinates the full control tower run lifecycle."""

from __future__ import annotations

import json
import logging
import time
import traceback
from datetime import datetime
from typing import Any

from agents.coder import CoderAgent
from agents.incident import IncidentAgent
from agents.planner import PlannerAgent
from agents.release import ReleaseAgent
from agents.reviewer import ReviewerAgent
from agents.security import SecurityAgent
from core.artifacts import ArtifactManager
from core.database import Database
from core.policy_engine import PolicyEngine
from core.risk_engine import RiskEngine
from core.state_machine import StateMachine
from schemas.coder import CoderInput
from schemas.common import GateDecision, RunStatus
from schemas.incident import IncidentInput
from schemas.planner import PlannerInput
from schemas.release import ReleaseInput
from schemas.reviewer import ReviewerInput
from schemas.security import SecurityInput
from tools.deploy_simulator import DeploymentSimulator
from tools.git_ops import GitOps
from tools.llm_client import OllamaClient
from tools.patch_apply import PatchApplicator
from tools.repo_scanner import RepoScanner
from tools.validation_runner import ValidationPipeline

logger = logging.getLogger(__name__)


class Orchestrator:
    """Coordinates the full AI-native software delivery pipeline.

    Lifecycle:
    1. PLANNING  → LLM-powered plan generation
    2. CODING    → LLM-powered code change generation
    3. VALIDATING → Automated test/lint/security pipeline
    4. REVIEWING  → LLM-powered code review
    5. RISK_SCORING → Rule-based risk assessment
    6. GATING → Deployment gate decision
    7. DEPLOYING → Canary deployment simulation
    8. MONITORING → Metric monitoring and regression detection
    9. ROLLING_BACK → Rollback on regression (if needed)
    10. COMPLETED / FAILED / BLOCKED
    """

    def __init__(
        self,
        db: Database,
        policy: PolicyEngine,
        artifacts: ArtifactManager,
        llm_client: OllamaClient | None = None,
    ):
        self.db = db
        self.policy = policy
        self.artifacts = artifacts
        self.llm = llm_client or OllamaClient(
            model=policy.get("llm.model", "qwen2.5-coder:7b"),
            fallback_model=policy.get("llm.fallback_model", "llama3:8b"),
            temperature=policy.get("llm.temperature", 0.2),
            max_tokens=policy.get("llm.max_tokens", 4096),
            max_retries=policy.get("llm.max_retries", 3),
            timeout=policy.get("llm.timeout_seconds", 120),
        )

        # Initialize agents
        self.planner = PlannerAgent(self.llm)
        self.coder = CoderAgent(self.llm)
        self.reviewer = ReviewerAgent(self.llm)
        self.security_agent = SecurityAgent()
        self.release_agent = ReleaseAgent()
        self.incident_agent = IncidentAgent()
        self.risk_engine = RiskEngine(self.policy)

    async def execute_run(
        self,
        run_id: str,
        task_id: str,
        task_title: str,
        task_description: str,
        repo_path: str,
    ) -> dict[str, Any]:
        """Execute a full control tower run.

        Returns a comprehensive result summary.
        """
        state_machine = StateMachine()
        start_time = time.time()
        result: dict[str, Any] = {
            "run_id": run_id,
            "task_id": task_id,
            "status": "pending",
            "stages": {},
            "error": None,
        }

        try:
            # ── Stage 1: PLANNING ─────────────────────────────
            state_machine.transition(RunStatus.PLANNING)
            self.db.update_run_status(run_id, "planning", "planning")
            self.db.record_state_transition(run_id, "planning")

            scanner = RepoScanner(repo_path)
            repo_summary = scanner.get_summary()
            file_tree = scanner.get_file_tree()

            planner_input = PlannerInput(
                task_title=task_title,
                task_description=task_description,
                repo_summary=repo_summary,
                file_tree=file_tree,
                key_modules=repo_summary.get("key_modules", []),
                language=repo_summary.get("language", "python"),
                policy_constraints={
                    "max_files": self.policy.autonomous_config.get("max_files_changed", 5),
                    "blocked_paths": self.policy.blocked_paths_config.get("files", []),
                },
            )

            plan_output, plan_retries = self.planner.plan(planner_input)

            # Store artifacts
            self.artifacts.store_report(run_id, "plan", plan_output.model_dump())
            self.db.store_agent_output(
                run_id, "planner", plan_output.model_dump(),
                schema_valid=True, retry_count=plan_retries,
            )

            result["stages"]["planning"] = {
                "status": "completed",
                "steps": len(plan_output.implementation_steps),
                "candidate_files": plan_output.candidate_files,
                "risk_estimate": plan_output.estimated_risk.value,
                "confidence": plan_output.confidence,
                "retries": plan_retries,
            }

            # ── Stage 2: CODING ───────────────────────────────
            state_machine.transition(RunStatus.CODING)
            self.db.update_run_status(run_id, "coding", "coding")
            self.db.record_state_transition(run_id, "coding")

            # Read target files
            target_files = scanner.get_multiple_files(plan_output.candidate_files)

            coder_input = CoderInput(
                task_summary=plan_output.task_summary,
                implementation_steps=[
                    s.model_dump() for s in plan_output.implementation_steps
                ],
                target_files=target_files,
                blocked_paths=self.policy.blocked_paths_config.get("files", []),
                max_files=self.policy.autonomous_config.get("max_files_changed", 5),
                max_patch_lines=self.policy.autonomous_config.get("max_patch_size_lines", 500),
            )

            code_output, code_retries = self.coder.generate_patch(coder_input)

            # Validate patch safety
            changed_files = [fc.file_path for fc in code_output.files_changed]
            violations = self.policy.validate_patch_safety(
                changed_files, code_output.total_lines_changed
            )

            if violations:
                violation_msgs = [str(v) for v in violations]
                logger.warning(f"Policy violations detected: {violation_msgs}")
                result["stages"]["coding"] = {
                    "status": "blocked",
                    "violations": violation_msgs,
                }
                state_machine.transition(RunStatus.BLOCKED)
                self.db.update_run_status(
                    run_id, "blocked", "blocked",
                    error=f"Policy violations: {violation_msgs}"
                )
                result["status"] = "blocked"
                return result

            # Apply patch
            patch_applicator = PatchApplicator(
                repo_path,
                blocked_paths=self.policy.blocked_paths_config.get("files", []),
            )

            # Create a Git branch for this run
            try:
                git = GitOps(repo_path)
                branch_name = f"control-tower/run-{run_id[:8]}"
                git.create_branch(branch_name)
            except Exception as e:
                logger.warning(f"Git branch creation failed: {e}")

            # Apply file changes
            apply_result = patch_applicator.apply_file_changes(
                [fc.model_dump() for fc in code_output.files_changed]
            )

            # Store artifacts
            self.artifacts.store_diff(run_id, code_output.patch_diff or "")
            self.artifacts.store_report(run_id, "code_changes", code_output.model_dump())
            self.db.store_agent_output(
                run_id, "coder", code_output.model_dump(),
                schema_valid=True, retry_count=code_retries,
            )

            result["stages"]["coding"] = {
                "status": "completed",
                "files_changed": len(code_output.files_changed),
                "lines_changed": code_output.total_lines_changed,
                "confidence": code_output.confidence,
                "retries": code_retries,
                "apply_result": apply_result,
            }

            # ── Stage 3: VALIDATING ───────────────────────────
            state_machine.transition(RunStatus.VALIDATING)
            self.db.update_run_status(run_id, "validating", "validating")
            self.db.record_state_transition(run_id, "validating")

            pipeline = ValidationPipeline(repo_path)
            validation_report = pipeline.run_all(run_id)

            # Store validation results
            self.artifacts.store_report(
                run_id, "validation_report", validation_report.model_dump()
            )
            for vr in validation_report.results:
                self.db.store_validation_result(
                    run_id=run_id,
                    tool_name=vr.tool_name,
                    status=vr.status.value,
                    passed=vr.passed,
                    return_code=vr.return_code,
                    duration_seconds=vr.duration_seconds,
                    summary=vr.summary,
                    findings_count=vr.findings_count,
                )

            result["stages"]["validation"] = {
                "status": "completed",
                "all_passed": validation_report.all_passed,
                "results": {r.tool_name: r.passed for r in validation_report.results},
                "blocking_failures": validation_report.blocking_failures,
                "duration": validation_report.total_duration_seconds,
            }

            # ── Stage 4: REVIEWING ────────────────────────────
            state_machine.transition(RunStatus.REVIEWING)
            self.db.update_run_status(run_id, "reviewing", "reviewing")
            self.db.record_state_transition(run_id, "reviewing")

            reviewer_input = ReviewerInput(
                task_description=task_description,
                planner_summary=plan_output.task_summary,
                patch_diff=code_output.patch_diff,
                files_changed=changed_files,
            )

            review_output, review_retries = self.reviewer.review(reviewer_input)

            self.artifacts.store_report(run_id, "review", review_output.model_dump())
            self.db.store_agent_output(
                run_id, "reviewer", review_output.model_dump(),
                schema_valid=True, retry_count=review_retries,
            )

            # Security analysis
            bandit_result = next(
                (r for r in validation_report.results if r.tool_name == "bandit"),
                None,
            )
            audit_result = next(
                (r for r in validation_report.results if r.tool_name == "pip-audit"),
                None,
            )

            security_input = SecurityInput(
                bandit_results=json.loads(bandit_result.raw_output)
                if bandit_result and bandit_result.raw_output
                else {},
                pip_audit_results=json.loads(audit_result.raw_output)
                if audit_result and audit_result.raw_output
                else {},
                patch_diff=code_output.patch_diff,
                changed_files=changed_files,
            )
            security_output = self.security_agent.analyze(security_input)

            self.artifacts.store_report(
                run_id, "security_report", security_output.model_dump()
            )

            result["stages"]["review"] = {
                "status": "completed",
                "findings": len(review_output.findings),
                "recommendation": review_output.recommendation,
                "security_findings": security_output.total_findings,
                "security_max_severity": security_output.max_severity.value,
            }

            # ── Stage 5: RISK SCORING ─────────────────────────
            state_machine.transition(RunStatus.RISK_SCORING)
            self.db.update_run_status(run_id, "risk_scoring", "risk_scoring")
            self.db.record_state_transition(run_id, "risk_scoring")

            # Get validation pass status
            test_passed = any(
                r.tool_name == "pytest" and r.passed
                for r in validation_report.results
            )
            lint_passed = any(
                r.tool_name == "ruff" and r.passed
                for r in validation_report.results
            )
            type_check_passed = any(
                r.tool_name == "mypy" and r.passed
                for r in validation_report.results
            )

            # Build security finding counts
            sec_counts: dict[str, int] = {}
            for sf in security_output.findings:
                sev = sf.severity.value
                sec_counts[sev] = sec_counts.get(sev, 0) + 1

            risk_assessment = self.risk_engine.compute(
                files_changed=len(changed_files),
                changed_paths=changed_files,
                test_passed=test_passed,
                lint_passed=lint_passed,
                type_check_passed=type_check_passed,
                security_findings=sec_counts,
                agent_confidence=min(
                    plan_output.confidence, code_output.confidence
                ),
                patch_lines=code_output.total_lines_changed,
            )

            self.db.store_risk_assessment(
                run_id=run_id,
                risk_score=risk_assessment.risk_score,
                risk_level=risk_assessment.risk_level,
                explanation=risk_assessment.explanation,
                contributing_factors=risk_assessment.contributing_factors,
                gate_recommendation=risk_assessment.gate_recommendation,
            )
            self.artifacts.store_report(
                run_id, "risk_assessment", risk_assessment.model_dump()
            )

            result["stages"]["risk_scoring"] = {
                "status": "completed",
                "risk_score": risk_assessment.risk_score,
                "risk_level": risk_assessment.risk_level,
                "gate_recommendation": risk_assessment.gate_recommendation,
                "factors": len(risk_assessment.contributing_factors),
            }

            # ── Stage 6: GATING ───────────────────────────────
            state_machine.transition(RunStatus.GATING)
            self.db.update_run_status(run_id, "gating", "gating")
            self.db.record_state_transition(run_id, "gating")

            release_input = ReleaseInput(
                risk_score=risk_assessment.risk_score,
                risk_level=risk_assessment.risk_level,
                validation_passed=validation_report.all_passed,
                validation_summary={
                    r.tool_name: r.passed for r in validation_report.results
                },
                security_block=security_output.block_recommended,
                security_max_severity=security_output.max_severity.value,
                reviewer_recommendation=review_output.recommendation,
            )

            release_output = self.release_agent.evaluate(release_input)

            self.artifacts.store_report(
                run_id, "gate_decision", release_output.model_dump()
            )

            result["stages"]["gating"] = {
                "status": "completed",
                "decision": release_output.gate_decision.value,
                "reasons": release_output.decision_reasons,
            }

            # Handle gate decision
            if release_output.gate_decision == GateDecision.BLOCK:
                state_machine.transition(RunStatus.BLOCKED)
                self.db.update_run_status(run_id, "blocked", "blocked")
                result["status"] = "blocked"
                result["gate_decision"] = "block"
                return result

            if release_output.gate_decision == GateDecision.HUMAN_REVIEW:
                state_machine.transition(RunStatus.AWAITING_APPROVAL)
                self.db.update_run_status(
                    run_id, "awaiting_approval", "awaiting_approval"
                )
                result["status"] = "awaiting_approval"
                result["gate_decision"] = "human_review"
                return result

            if release_output.gate_decision == GateDecision.APPROVE:
                state_machine.transition(RunStatus.COMPLETED)
                self.db.update_run_status(run_id, "completed", "completed")
                result["status"] = "completed"
                result["gate_decision"] = "approve"
                return result

            # ── Stage 7: DEPLOYING (Canary) ───────────────────
            state_machine.transition(RunStatus.DEPLOYING)
            self.db.update_run_status(run_id, "deploying", "deploying")
            self.db.record_state_transition(run_id, "deploying")

            deployment = self.db.create_deployment(run_id, "canary")

            simulator = DeploymentSimulator(
                canary_duration=self.policy.get_canary_duration(),
                check_interval=self.policy.get_canary_interval(),
                metrics_config=self.policy.get_canary_metrics_config(),
            )

            # Simulate canary (determine if degradation should be simulated
            # based on risk level)
            simulate_degradation = risk_assessment.risk_level in ("medium", "high")

            # ── Stage 8: MONITORING ───────────────────────────
            state_machine.transition(RunStatus.MONITORING)
            self.db.update_run_status(run_id, "monitoring", "monitoring")
            self.db.record_state_transition(run_id, "monitoring")

            canary_result = simulator.simulate_canary(
                simulate_degradation=simulate_degradation,
            )

            self.db.update_deployment(
                deployment.id,
                status=canary_result["status"],
                baseline_metrics=canary_result["baseline_metrics"],
                canary_metrics=canary_result["final_canary_metrics"],
                rollback_triggered=canary_result["rollback_triggered"],
            )

            self.artifacts.store_report(
                run_id, "canary_report", canary_result
            )

            result["stages"]["canary"] = {
                "status": canary_result["status"],
                "windows": canary_result["total_windows"],
                "rollback_triggered": canary_result["rollback_triggered"],
            }

            # ── Incident Handling ─────────────────────────────
            if canary_result["rollback_triggered"]:
                state_machine.transition(RunStatus.ROLLING_BACK)
                self.db.update_run_status(run_id, "rolling_back", "rolling_back")
                self.db.record_state_transition(run_id, "rolling_back")

                # Build threshold breach details
                breaches = []
                for metric_name, count in canary_result["breach_counts"].items():
                    if count > 0:
                        breaches.append({
                            "metric": metric_name,
                            "count": count,
                            "threshold": count,
                        })

                incident_input = IncidentInput(
                    baseline_metrics=canary_result["baseline_metrics"],
                    canary_metrics=canary_result["final_canary_metrics"],
                    patch_summary=code_output.rationale,
                    threshold_breaches=breaches,
                    deployment_id=deployment.id,
                )

                incident_output = self.incident_agent.analyze(incident_input)

                self.db.create_incident(
                    run_id=run_id,
                    deployment_id=deployment.id,
                    anomaly_detected=incident_output.anomaly_detected,
                    action_taken=incident_output.action_recommendation,
                    summary=incident_output.incident_summary,
                    postmortem_draft=incident_output.postmortem_draft,
                    metrics=[m.model_dump() for m in incident_output.metrics_summary],
                )

                self.artifacts.store_report(
                    run_id, "incident_report", incident_output.model_dump()
                )

                result["stages"]["incident"] = {
                    "anomaly": incident_output.anomaly_detected,
                    "action": incident_output.action_recommendation,
                    "probable_causes": incident_output.probable_causes,
                }

                # Simulate rollback
                try:
                    git = GitOps(repo_path)
                    git.reset_hard("HEAD~1")
                    logger.info("Rollback: reset to previous commit")
                except Exception as e:
                    logger.warning(f"Rollback git reset failed: {e}")

            # ── Complete ──────────────────────────────────────
            state_machine.transition(RunStatus.COMPLETED)
            self.db.update_run_status(run_id, "completed", "completed")
            result["status"] = "completed" if not canary_result["rollback_triggered"] else "rolled_back"

        except Exception as e:
            logger.error(f"Run failed: {e}\n{traceback.format_exc()}")
            result["status"] = "failed"
            result["error"] = str(e)
            result["traceback"] = traceback.format_exc()

            try:
                self.db.update_run_status(run_id, "failed", "failed", error=str(e))
            except Exception:
                pass

        finally:
            elapsed = time.time() - start_time
            result["duration_seconds"] = round(elapsed, 2)
            result["state_history"] = state_machine.get_history()

            # Store final result
            self.artifacts.store_report(run_id, "run_result", result)

        return result
