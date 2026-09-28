"""Output formats for ``python -m rt_dialogs output <format>``.

A format is an object with ``name``, ``help``, ``add_arguments(parser)`` and
``run(db, args) -> exit code``. Register new formats in ``FORMATS``.
"""

from .explorer_bundle import ExplorerBundle
from .labeled_script import LabeledScriptSingle

FORMATS = {f.name: f for f in (LabeledScriptSingle, ExplorerBundle)}
