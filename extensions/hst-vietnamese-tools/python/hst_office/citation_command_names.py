# SPDX-License-Identifier: AGPL-3.0-only
"""Names of the citation commands (org.hst.office.vi:<name>), kept apart from citation_actions so the dispatcher
can answer for them without importing any citation code (it is asked about every HST menu item at start-up).
The ribbon's "Trích dẫn" group, the HST menu, Alt+Shift+I and feature search use exactly these URLs."""
NAMES = frozenset(("CitationInsert", "CitationReinsert", "CitationBibliography", "CitationUpdate", "CitationStyle",
                   "CitationLibrary"))
