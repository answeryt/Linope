"""Model scheduler compatibility implementation.

The implementation is kept import-compatible with older callers while the
package name moves from ``llm_scheduler`` to ``model_scheduler``.
"""

from kernel.scheduler.llm_scheduler.drive import (
    Drive,
    Turn,
    is_model_line,
    is_model_process,
)

__all__ = ["Drive", "Turn", "is_model_line", "is_model_process"]
