from __future__ import annotations

from .cancel import OpenCodeCancelMixin
from .state import initialize_reader
from .storage import OpenCodeStorageMixin
from .timeline import OpenCodeTimelineMixin


class OpenCodeLogReader(OpenCodeStorageMixin, OpenCodeTimelineMixin, OpenCodeCancelMixin):
    def __init__(
        self,
        root=None,
        work_dir=None,
        project_id: str = "global",
        *,
        session_id_filter: str | None = None,
    ):
        initialize_reader(
            self,
            root=root,
            work_dir=work_dir,
            project_id=project_id,
            session_id_filter=session_id_filter,
        )


__all__ = ['OpenCodeLogReader']
