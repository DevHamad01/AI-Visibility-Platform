"""Pipeline-level exceptions. Raised by a node (to be caught by `run_node`,
app.pipeline.stages) when the node itself should be marked `failed` — as
opposed to a per-call failure within a node that still had other successes
and should just be logged, not fail the whole stage.
"""

from __future__ import annotations


class StageFailedError(Exception):
    """Every external call this node attempted failed — there is nothing
    useful to report as a success for this stage."""
