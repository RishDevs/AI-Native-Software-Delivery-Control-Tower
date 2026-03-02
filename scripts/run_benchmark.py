"""Benchmark runner — executes tasks and collects metrics."""

from __future__ import annotations

import json
import logging
import os
import sys
import time
import yaml
from datetime import datetime
from pathlib import Path
from typing import Any

# Add project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.database import Database
from core.policy_engine import PolicyEngine
from core.artifacts import ArtifactManager
from core.orchestrator import Orchestrator
from tools.llm_client import OllamaClient

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)-20s | %(levelname)-8s | %(message)s",
)


def load_benchmark_tasks(tasks_file: str = "benchmarks/tasks/benchmark_tasks.yaml") -> list[dict]:
    """Load benchmark tasks from YAML."""
    with open(tasks_file) as f:
        data = yaml.safe_load(f)
    return data.get("tasks", [])


def run_benchmarks(
    tasks_file: str = "benchmarks/tasks/benchmark_tasks.yaml",
    repo_path: str = "./demo_target_repo",
    max_tasks: int | None = None,
    categories: list[str] | None = None,
) -> dict[str, Any]:
    """Execute benchmark tasks and collect metrics."""
    tasks = load_benchmark_tasks(tasks_file)

    if categories:
        tasks = [t for t in tasks if t.get("category") in categories]
    if max_tasks:
        tasks = tasks[:max_tasks]

    logger.info(f"Running {len(tasks)} benchmark tasks")

    # Initialize components
    db = Database("benchmark.db")
    db.create_tables()

    policy = PolicyEngine("configs/policy.yaml")
    artifacts = ArtifactManager("./artifacts/benchmarks", db)

    # Results collection
    results: list[dict[str, Any]] = []
    metrics = {
        "total_tasks": len(tasks),
        "completed": 0,
        "failed": 0,
        "blocked": 0,
        "total_duration": 0,
        "category_results": {},
    }

    for i, task in enumerate(tasks, 1):
        task_id = task["id"]
        logger.info(f"\n{'='*60}")
        logger.info(f"Task {i}/{len(tasks)}: [{task_id}] {task['title']}")
        logger.info(f"Category: {task['category']} | Difficulty: {task.get('difficulty', 'unknown')}")
        logger.info(f"{'='*60}")

        start_time = time.time()

        try:
            # Create task in DB
            db_task = db.create_task(
                title=task["title"],
                description=task["description"],
                repo_path=os.path.abspath(repo_path),
                metadata={"benchmark_id": task_id, "category": task["category"]},
            )

            # Create and execute run
            run = db.create_run(db_task.id, metadata={"benchmark": True})

            llm = OllamaClient(
                model=policy.get("llm.model", "qwen2.5-coder:7b"),
                max_retries=policy.get("llm.max_retries", 3),
                timeout=policy.get("llm.timeout_seconds", 120),
            )

            orchestrator = Orchestrator(db, policy, artifacts, llm)

            import asyncio
            result = asyncio.run(orchestrator.execute_run(
                run_id=run.id,
                task_id=db_task.id,
                task_title=task["title"],
                task_description=task["description"],
                repo_path=os.path.abspath(repo_path),
            ))

            duration = time.time() - start_time

            task_result = {
                "task_id": task_id,
                "title": task["title"],
                "category": task["category"],
                "difficulty": task.get("difficulty", "unknown"),
                "status": result.get("status", "unknown"),
                "duration_seconds": round(duration, 2),
                "stages": result.get("stages", {}),
                "error": result.get("error"),
            }

            results.append(task_result)

            # Update metrics
            status = result.get("status", "failed")
            if status == "completed":
                metrics["completed"] += 1
            elif status == "blocked":
                metrics["blocked"] += 1
            else:
                metrics["failed"] += 1

            metrics["total_duration"] += duration

            cat = task["category"]
            if cat not in metrics["category_results"]:
                metrics["category_results"][cat] = {"total": 0, "completed": 0, "failed": 0}
            metrics["category_results"][cat]["total"] += 1
            if status == "completed":
                metrics["category_results"][cat]["completed"] += 1
            else:
                metrics["category_results"][cat]["failed"] += 1

            logger.info(f"Result: {status} ({duration:.1f}s)")

        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"Task {task_id} crashed: {e}")
            results.append({
                "task_id": task_id,
                "title": task["title"],
                "category": task["category"],
                "status": "error",
                "duration_seconds": round(duration, 2),
                "error": str(e),
            })
            metrics["failed"] += 1

    # Generate summary
    metrics["completion_rate"] = (
        metrics["completed"] / metrics["total_tasks"]
        if metrics["total_tasks"] > 0
        else 0
    )
    metrics["average_duration"] = (
        metrics["total_duration"] / metrics["total_tasks"]
        if metrics["total_tasks"] > 0
        else 0
    )

    # Save results
    results_dir = Path("benchmarks/results")
    results_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    results_file = results_dir / f"benchmark_{timestamp}.json"

    with open(results_file, "w") as f:
        json.dump(
            {"metrics": metrics, "results": results, "timestamp": timestamp},
            f, indent=2,
        )

    logger.info(f"\n{'='*60}")
    logger.info("BENCHMARK SUMMARY")
    logger.info(f"{'='*60}")
    logger.info(f"Total tasks: {metrics['total_tasks']}")
    logger.info(f"Completed: {metrics['completed']}")
    logger.info(f"Failed: {metrics['failed']}")
    logger.info(f"Blocked: {metrics['blocked']}")
    logger.info(f"Completion rate: {metrics['completion_rate']:.1%}")
    logger.info(f"Total duration: {metrics['total_duration']:.1f}s")
    logger.info(f"Avg duration: {metrics['average_duration']:.1f}s")
    logger.info(f"Results saved: {results_file}")

    return {"metrics": metrics, "results": results}


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run benchmark tasks")
    parser.add_argument("--tasks-file", default="benchmarks/tasks/benchmark_tasks.yaml")
    parser.add_argument("--repo-path", default="./demo_target_repo")
    parser.add_argument("--max-tasks", type=int, default=None)
    parser.add_argument("--categories", nargs="+", default=None)
    args = parser.parse_args()

    run_benchmarks(
        tasks_file=args.tasks_file,
        repo_path=args.repo_path,
        max_tasks=args.max_tasks,
        categories=args.categories,
    )
