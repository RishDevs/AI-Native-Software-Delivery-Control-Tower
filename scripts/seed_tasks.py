"""Seed initial tasks into the database for demonstration."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.database import Database


DEMO_TASKS = [
    {
        "title": "Fix case-sensitive product search",
        "description": (
            "The search_products function uses case-sensitive string matching. "
            "Users searching for 'widget' won't find 'Widget'. "
            "Fix the search to be case-insensitive."
        ),
        "repo_path": "./demo_target_repo",
    },
    {
        "title": "Fix missing discount validation",
        "description": (
            "The calculate_discount function accepts negative discount percentages "
            "and values over 100%, producing incorrect prices. Add validation to "
            "reject discount_percent < 0 or > 100."
        ),
        "repo_path": "./demo_target_repo",
    },
    {
        "title": "Add pagination to list products endpoint",
        "description": (
            "The GET /products endpoint returns all products without pagination. "
            "Add limit and offset query parameters with defaults (limit=20, offset=0)."
        ),
        "repo_path": "./demo_target_repo",
    },
    {
        "title": "Fix min_price filter operator",
        "description": (
            "The list_products endpoint uses > instead of >= for min_price filtering. "
            "Products priced exactly at min_price are excluded. Fix to use >=."
        ),
        "repo_path": "./demo_target_repo",
    },
    {
        "title": "Add proper HTTP 201 status for product creation",
        "description": (
            "The POST /products endpoint returns 200 instead of 201 Created. "
            "Fix the response to return the correct HTTP status code."
        ),
        "repo_path": "./demo_target_repo",
    },
]


def seed_tasks():
    """Seed demo tasks into the database."""
    db = Database("control_tower.db")
    db.create_tables()

    for task_data in DEMO_TASKS:
        task = db.create_task(**task_data)
        print(f"Created task: [{task.id[:8]}] {task.title}")

    print(f"\nSeeded {len(DEMO_TASKS)} tasks successfully.")
    print("Start a run with: POST http://localhost:8000/runs")


if __name__ == "__main__":
    seed_tasks()
