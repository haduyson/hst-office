# SPDX-License-Identifier: AGPL-3.0-only
"""Configuration data of the bundled extension names every node once among its siblings.

Two branches that each register a job for the same document event both add an Events/OnLoad node to Jobs.xcu; git
merges that without a conflict, and the file then holds two sibling OnLoad nodes. Tests that look the event up by name
see only one of them and a later edit easily drops a job. One node per event, holding every job, is the only form."""
import collections
import glob
import os
import unittest
import xml.etree.ElementTree as ET

import _paths

EXT = os.path.join(_paths.ROOT, "extensions", "hst-vietnamese-tools")
OOR_NAME = "{http://openoffice.org/2001/registry}name"


def duplicate_siblings(path):
    """[(parent name, child name, count)] for child nodes that share a name under one parent."""
    found = []
    for parent in ET.parse(path).getroot().iter():
        names = collections.Counter(child.get(OOR_NAME) for child in parent if child.tag == "node")
        found += [(parent.get(OOR_NAME), name, count) for name, count in sorted(names.items()) if count > 1]
    return found


class UniqueNodes(unittest.TestCase):
    def test_jobs_has_one_node_per_event(self):
        root = ET.parse(os.path.join(EXT, "Jobs.xcu")).getroot()
        events = [node for node in root if node.get(OOR_NAME) == "Events"]
        self.assertEqual(len(events), 1)
        names = collections.Counter(node.get(OOR_NAME) for node in events[0] if node.tag == "node")
        self.assertEqual(names["OnLoad"], 1)
        self.assertEqual([name for name, count in names.items() if count > 1], [])

    def test_no_xcu_repeats_a_sibling_node(self):
        files = sorted(glob.glob(os.path.join(EXT, "**", "*.xcu"), recursive=True))
        self.assertTrue(files)
        for path in files:
            self.assertEqual(duplicate_siblings(path), [], os.path.relpath(path, EXT))

    def test_the_check_sees_a_repeated_event(self):
        import tempfile
        text = ('<oor:component-data xmlns:oor="http://openoffice.org/2001/registry" oor:name="Jobs" '
                'oor:package="org.openoffice.Office"><node oor:name="Events">'
                '<node oor:name="OnLoad" oor:op="fuse"/><node oor:name="OnLoad" oor:op="fuse"/>'
                '</node></oor:component-data>')
        with tempfile.NamedTemporaryFile("w", suffix=".xcu", delete=False, encoding="utf-8") as handle:
            handle.write(text)
        try:
            self.assertEqual(duplicate_siblings(handle.name), [("Events", "OnLoad", 2)])
        finally:
            os.unlink(handle.name)


if __name__ == "__main__":
    unittest.main()
