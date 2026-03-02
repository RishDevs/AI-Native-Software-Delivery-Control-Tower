"""Security Agent — aggregates tool-based security findings (primarily rule-based)."""

from __future__ import annotations

import json
import logging
from typing import Any

from schemas.security import SecurityInput, SecurityOutput, SecurityFinding
from schemas.common import Severity

logger = logging.getLogger(__name__)


class SecurityAgent:
    """Deterministic/rule-based agent that normalizes security scan outputs.

    For MVP, this agent is mostly tool-driven rather than LLM-driven,
    ensuring reliable and fast security evaluation.
    """

    def analyze(self, input_data: SecurityInput) -> SecurityOutput:
        """Analyze security scan results and produce normalized findings."""
        findings: list[SecurityFinding] = []

        # Process Bandit results
        bandit_findings = self._process_bandit(input_data.bandit_results)
        findings.extend(bandit_findings)

        # Process pip-audit results
        audit_findings = self._process_pip_audit(input_data.pip_audit_results)
        findings.extend(audit_findings)

        # Determine max severity
        severity_order = {
            Severity.INFO: 0,
            Severity.LOW: 1,
            Severity.MEDIUM: 2,
            Severity.HIGH: 3,
            Severity.CRITICAL: 4,
        }
        max_sev = Severity.INFO
        for f in findings:
            if severity_order.get(f.severity, 0) > severity_order.get(max_sev, 0):
                max_sev = f.severity

        # Determine if blocking
        block = max_sev in (Severity.HIGH, Severity.CRITICAL)

        # Build remediation notes
        remediation = []
        for f in findings:
            if f.severity in (Severity.HIGH, Severity.CRITICAL) and f.remediation:
                remediation.append(f"[{f.severity.value}] {f.description}: {f.remediation}")

        summary_parts = [
            f"Total findings: {len(findings)}",
            f"Max severity: {max_sev.value}",
            f"Block recommended: {block}",
        ]

        logger.info(f"Security analysis: {len(findings)} findings, max={max_sev.value}")

        return SecurityOutput(
            findings=findings,
            max_severity=max_sev,
            total_findings=len(findings),
            block_recommended=block,
            remediation_notes=remediation,
            summary="\n".join(summary_parts),
            confidence=0.9,  # High confidence for tool-based analysis
        )

    def _process_bandit(self, bandit_results: dict) -> list[SecurityFinding]:
        """Process Bandit scan results into normalized findings."""
        findings = []

        results = bandit_results.get("results", [])
        if isinstance(results, str):
            try:
                results = json.loads(results)
            except json.JSONDecodeError:
                return findings

        for result in results:
            severity_map = {
                "LOW": Severity.LOW,
                "MEDIUM": Severity.MEDIUM,
                "HIGH": Severity.HIGH,
            }
            sev_str = result.get("issue_severity", "LOW").upper()
            severity = severity_map.get(sev_str, Severity.LOW)

            findings.append(SecurityFinding(
                tool="bandit",
                rule_id=result.get("test_id", ""),
                severity=severity,
                file_path=result.get("filename", ""),
                line_number=result.get("line_number"),
                description=result.get("issue_text", ""),
                remediation=result.get("more_info", ""),
                cwe=result.get("issue_cwe", {}).get("id", "") if isinstance(
                    result.get("issue_cwe"), dict
                ) else "",
            ))

        return findings

    def _process_pip_audit(self, audit_results: dict) -> list[SecurityFinding]:
        """Process pip-audit results into normalized findings."""
        findings = []

        vulnerabilities = audit_results.get("vulnerabilities", [])
        if isinstance(vulnerabilities, str):
            try:
                vulnerabilities = json.loads(vulnerabilities)
            except json.JSONDecodeError:
                return findings

        for vuln in vulnerabilities:
            # Map CVSS score to severity
            fix_versions = vuln.get("fix_versions", [])
            remediation = f"Upgrade to {', '.join(fix_versions)}" if fix_versions else ""

            findings.append(SecurityFinding(
                tool="pip-audit",
                rule_id=vuln.get("id", ""),
                severity=Severity.HIGH,  # Dependency vulns are generally high
                description=f"{vuln.get('name', '')}: {vuln.get('description', '')}",
                remediation=remediation,
            ))

        return findings
