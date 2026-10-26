from __future__ import annotations

import threading

from typing import Any, Callable, Sequence

from deepwrap.function_calling import Tool


STATUSES = ("pending", "in_progress", "done", "blocked")

# Plans longer than this stop being a plan and start being a transcript.
MAX_STEPS = 12

# How much of a step title is kept. Titles are repeated in every recap, so they
# have to stay short.
MAX_TITLE_CHARS = 120


class TaskPlan:
    """An explicit, ordered plan the agent keeps in context while it works.

    A weaker model drifts over a long tool loop: it forgets what it set out to
    do, redoes finished work, or stops early. Writing the plan down as tool
    state, and replaying it with every progress recap, keeps the goal and the
    position in it inside the context window instead of in the model's memory.
    """

    def __init__(self) -> None:
        self._steps: list[dict[str, Any]] = []
        self._lock = threading.RLock()

    # -- tool implementations -------------------------------------------------

    def set_plan(self, steps: Sequence[str]) -> dict[str, Any]:
        """Replace the current plan with an ordered list of concrete steps."""

        if not steps:
            raise ValueError("A plan needs at least one step.")
        if len(steps) > MAX_STEPS:
            raise ValueError(
                f"A plan may hold at most {MAX_STEPS} steps; "
                "group the small ones together."
            )
        with self._lock:
            self._steps = [
                {
                    "index": index,
                    "title": str(title).strip()[:MAX_TITLE_CHARS],
                    "status": "pending",
                    "note": None,
                }
                for index, title in enumerate(steps, 1)
            ]
            if self._steps:
                self._steps[0]["status"] = "in_progress"
            return self.get_plan()

    def update_plan(
        self,
        step: int,
        status: str,
        note: str | None = None,
    ) -> dict[str, Any]:
        """Set one step's status, and start the next one when it is done."""

        if status not in STATUSES:
            raise ValueError(f"status must be one of {', '.join(STATUSES)}")
        with self._lock:
            if not self._steps:
                raise ValueError("No plan has been set; call set_plan first.")
            target = next((item for item in self._steps if item["index"] == step), None)
            if target is None:
                raise ValueError(
                    f"Step {step} does not exist; the plan has "
                    f"{len(self._steps)} steps."
                )
            target["status"] = status
            target["note"] = (note or "").strip()[:MAX_TITLE_CHARS] or None
            if status == "done":
                following = next(
                    (
                        item
                        for item in self._steps
                        if item["index"] > step and item["status"] == "pending"
                    ),
                    None,
                )
                if following is not None:
                    following["status"] = "in_progress"
            return self.get_plan()

    def get_plan(self) -> dict[str, Any]:
        """Return the plan with progress counters."""

        with self._lock:
            steps = [dict(item) for item in self._steps]
        done = sum(1 for item in steps if item["status"] == "done")
        current = next(
            (item["title"] for item in steps if item["status"] == "in_progress"),
            None,
        )
        return {
            "steps": steps,
            "total": len(steps),
            "done": done,
            "current": current,
            "complete": bool(steps) and done == len(steps),
        }

    # -- helpers --------------------------------------------------------------

    MARKS = {
        "done": "x",
        "in_progress": ">",
        "blocked": "!",
        "pending": " ",
    }

    def summary(self) -> str:
        """Render the plan as compact text for a progress recap."""

        with self._lock:
            if not self._steps:
                return ""
            lines = [
                f"[{self.MARKS[item['status']]}] {item['index']}. {item['title']}"
                + (f" ({item['note']})" if item["note"] else "")
                for item in self._steps
            ]
        return "\n".join(lines)

    def reset(self) -> None:
        """Drop the plan, for example when a new conversation starts."""

        with self._lock:
            self._steps = []

    # -- agent wiring ---------------------------------------------------------

    @property
    def definitions(self) -> tuple[Tool, ...]:
        return (
            Tool(
                "set_plan",
                "Write down an ordered plan before starting work that needs "
                "more than about three tool calls. Use 3 to 7 concrete, "
                "verifiable steps. Replaces any existing plan.",
                {
                    "type": "object",
                    "properties": {
                        "steps": {
                            "type": "array",
                            "items": {"type": "string"},
                            "maxItems": MAX_STEPS,
                        }
                    },
                    "required": ["steps"],
                },
            ),
            Tool(
                "update_plan",
                "Mark one plan step done, in_progress, or blocked as soon as "
                "its state changes. The next pending step starts automatically.",
                {
                    "type": "object",
                    "properties": {
                        "step": {"type": "integer", "minimum": 1},
                        "status": {"type": "string", "enum": list(STATUSES)},
                        "note": {"type": "string"},
                    },
                    "required": ["step", "status"],
                },
            ),
            Tool(
                "get_plan",
                "Read the current plan and how much of it is finished.",
                {"type": "object"},
            ),
        )

    @property
    def functions(self) -> dict[str, Callable[..., Any]]:
        return {
            "set_plan": self.set_plan,
            "update_plan": self.update_plan,
            "get_plan": self.get_plan,
        }
