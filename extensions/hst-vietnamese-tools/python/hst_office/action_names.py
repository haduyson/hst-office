# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""The names of the commands in actions.COMMANDS (org.hst.office.vi:<name>), for dispatch."""
from . import citation_command_names

# The commands of actions.COMMANDS, by name. The Start Center creates this handler and asks it about every HST menu
# item while the splash screen is still up; answering from names keeps the command code (actions: ND30, encodings,
# CSV, VBA, ...) out of every start. actions is imported when a command runs (tests/unit/test_dispatch_no_document.py
# checks that the names match).
ACTION_COMMANDS = frozenset((
    "Nd30Wizard", "ToggleDuplex", "ConvertEncoding", "FormatDate", "FormatDateLong", "FormatMonthYear", "FormatDateDash",
    "FormatVnd", "FormatPercent", "ImportCsv", "EditVba", "NumberToWords", "RemoveDiacritics", "SplitName",
    "SortByGivenName", "DeleteBlankRows", "PreviousVersions", "OpenInHstPdf", "ChemFormula", "ConvertFormulas",
    "AskConvertFormula", "FormulaTemplates", "NewEquation", "TexToggle")) | citation_command_names.NAMES
