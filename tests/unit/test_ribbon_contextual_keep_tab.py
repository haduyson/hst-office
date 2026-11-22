# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""The ribbon stays on a contextual tab while its object stays selected (hst-ribbon-contextual-keep-tab.patch):
vcl/inc/HstContextualKeepTab.hxx compiled with a driver that replays the context changes a command sends
through a model of NotebookbarTabControlBase::SetContext, and the patch's wiring into the tab control."""
import os
import shutil
import subprocess
import tempfile
import unittest

from patch_sections import added, sections

PATCH = "hst-ribbon-contextual-keep-tab.patch"
HEADER = "vcl/inc/HstContextualKeepTab.hxx"

# The model follows SetContext of the patched tab control: page visibility, the opening of a page by a
# non-selection context or after an insert command, the fall back to the default tab, then the keep step.
DRIVER = r"""
#include "HstContextualKeepTab.hxx"
#include <cstdio>
#include <initializer_list>
#include <set>
#include <string>
#include <vector>
using namespace hst::ribbon;
static int failures = 0;
#define CHECK(x) do { if (!(x)) { std::printf("FAIL %d %s\n", __LINE__, #x); ++failures; } } while (0)

struct Page { std::uint16_t id; std::string name; std::set<std::string> contexts; };

static bool isSelection(const std::string& c)
{
    static const std::set<std::string> s{ "Table", "Graphic", "Chart", "OLE", "Frame", "Media", "Draw",
                                          "DrawLine", "3DObject", "MultiObject", "Form", "Pivot" };
    return s.count(c) > 0;
}

struct Ribbon
{
    std::vector<Page> pages;
    std::uint16_t cur = 1;
    std::string last = "any";
    bool lastSupported = true;
    std::uint16_t kept = 0;
    bool insertNote = false;
    bool keep = true; // false: the tab control before the patch

    const Page* page(std::uint16_t id) const
    {
        for (const Page& p : pages)
            if (p.id == id)
                return &p;
        return nullptr;
    }
    static bool has(const Page* p, const std::string& c) { return p && p->contexts.count(c) > 0; }
    std::string current() const { return page(cur)->name; }

    void setContext(const std::string& ctx)
    {
        if (ctx == last)
            return;
        if (keep)
        {
            const Page* pKeep = page(cur);
            const bool bContextual = pKeep && last != "any" && !has(pKeep, "any") && has(pKeep, last);
            kept = keepTabBefore(kept, cur, bContextual);
        }
        bool opened = false;
        bool takeNote = false;
        if (isSelection(ctx))
        {
            takeNote = insertNote;
            insertNote = false;
        }
        const bool bSelection = isSelection(ctx) && !takeNote;
        bool handled = page(cur) && last != "any" && has(page(cur), "any");
        for (const Page& p : pages)
        {
            if (ctx != "any" && !bSelection && (!handled || !has(&p, "any")) && has(&p, ctx))
            {
                cur = p.id;
                handled = true;
                lastSupported = true;
                opened = opened || !has(&p, "any");
            }
            if (!handled && lastSupported && has(&p, "default"))
                cur = p.id;
        }
        if (!handled)
            lastSupported = false;
        last = ctx;
        if (!has(page(cur), ctx) && !has(page(cur), "any"))
            for (const Page& p : pages)
                if (has(&p, "default"))
                {
                    cur = p.id;
                    break;
                }
        if (keep && kept)
        {
            const std::uint16_t r = keepTabAfter(kept, cur, has(page(kept), ctx), opened);
            if (r)
                cur = r;
        }
    }
    void burst(std::initializer_list<const char*> contexts)
    {
        for (const char* c : contexts)
            setContext(c);
    }
    void idle() { kept = 0; } // the idle task forgets the remembered page
    void click(const std::string& name)
    {
        for (const Page& p : pages)
            if (p.name == name)
                cur = p.id;
    }
};

static Ribbon writer(bool keep = true)
{
    Ribbon r;
    r.keep = keep;
    r.pages = { { 1, "Home", { "default", "any", "Text", "DrawText" } },
                { 2, "Insert", { "any" } },
                { 3, "TableDesign", { "Table" } },
                { 4, "TableLayout", { "Table" } },
                { 5, "Picture", { "Graphic" } },
                { 6, "Shape", { "Draw", "DrawLine", "3DObject", "MultiObject" } },
                { 7, "Frame", { "Frame", "OLE" } },
                { 8, "Preview", { "Printpreview" } } };
    r.setContext("Text");
    r.idle();
    return r;
}

int main()
{
    // the pure decisions
    CHECK(keepTabBefore(0, 5, true) == 5);
    CHECK(keepTabBefore(5, 1, false) == 5);
    CHECK(keepTabBefore(0, 1, false) == 0);
    CHECK(keepTabAfter(5, 1, true, false) == 5);
    CHECK(keepTabAfter(5, 1, false, false) == 0);
    CHECK(keepTabAfter(5, 1, true, true) == 0);
    CHECK(keepTabAfter(5, 5, true, false) == 0);
    CHECK(keepTabAfter(0, 1, true, false) == 0);

    // the reported bug, before the patch: a command on the selected picture rebuilds Writer's shells
    // (Graphic, Default, Frame, Graphic) and the ribbon is left on Home
    {
        Ribbon r = writer(false);
        r.burst({ "Default", "Frame", "Graphic" });
        r.idle();
        CHECK(r.current() == "Home"); // selecting a picture leaves the ribbon on the current tab
        r.click("Picture");
        r.burst({ "Default", "Frame", "Graphic" });
        CHECK(r.current() == "Home");
    }
    // with the patch the Picture Format tab stays
    {
        Ribbon r = writer();
        r.burst({ "Default", "Frame", "Graphic" });
        r.idle();
        CHECK(r.current() == "Home");
        r.click("Picture");
        r.burst({ "Default", "Frame", "Graphic" });
        r.idle();
        CHECK(r.current() == "Picture");
        // a picture unmarked and marked again (Slides, Draw, Sheets: compress, replace, filter)
        r.burst({ "DrawPage", "Graphic" });
        r.idle();
        CHECK(r.current() == "Picture");
        // the picture is really deselected: back to Home, and a later selection does not open the tab
        r.burst({ "Default", "Text" });
        CHECK(r.current() == "Home");
        r.idle();
        r.burst({ "Default", "Frame", "Graphic" });
        r.idle();
        CHECK(r.current() == "Home");
    }
    // the second of two tabs of a context is the one that comes back (Table Layout, a row selected in Writer)
    {
        Ribbon r = writer();
        r.burst({ "Table" });
        r.idle();
        CHECK(r.current() == "Home");
        r.click("TableLayout");
        r.burst({ "Default", "Text", "Table" });
        r.idle();
        CHECK(r.current() == "TableLayout");
    }
    // the shape tab stays when the context moves between two contexts that both show it
    {
        Ribbon r = writer();
        r.burst({ "Draw" });
        r.click("Shape");
        r.burst({ "DrawLine" });
        r.idle();
        CHECK(r.current() == "Shape");
    }
    // an insert command opens the new object's tab; the remembered tab does not override it
    {
        Ribbon r = writer();
        r.burst({ "Table" });
        r.click("TableDesign");
        r.idle();
        r.insertNote = true;
        r.burst({ "Default", "Graphic" });
        r.idle();
        CHECK(r.current() == "Picture");
        r.insertNote = true; // a chart inserted while the picture tab is current
        r.burst({ "Default", "Chart" });
        CHECK(r.current() == "Home"); // the model has no chart page: the default tab, not the picture tab
        r.idle();
    }
    // a view mode opens its tab even while a contextual tab is remembered
    {
        Ribbon r = writer();
        r.burst({ "Graphic" });
        r.click("Picture");
        r.burst({ "Default", "Printpreview" });
        CHECK(r.current() == "Preview");
        r.idle();
    }
    // a tab the user picked (not contextual) is never replaced
    {
        Ribbon r = writer();
        r.burst({ "Graphic" });
        r.idle();
        r.click("Insert");
        r.burst({ "Default", "Frame", "Graphic" });
        r.idle();
        CHECK(r.current() == "Insert");
    }
    std::printf("checks done, %d failure(s)\n", failures);
    return failures ? 1 : 0;
}
"""


def new_file(path):
    return "\n".join(line[1:] for line in sections(PATCH)[path] if line.startswith("+")) + "\n"


class RibbonContextualKeepTab(unittest.TestCase):
    @unittest.skipUnless(shutil.which("g++"), "no C++ compiler")
    def test_contextual_tab_survives_a_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "HstContextualKeepTab.hxx"), "w", encoding="utf-8") as handle:
                handle.write(new_file(HEADER))
            with open(os.path.join(tmp, "driver.cxx"), "w", encoding="utf-8") as handle:
                handle.write(DRIVER)
            exe = os.path.join(tmp, "driver")
            subprocess.run(["g++", "-std=c++17", "-Wall", "-Werror", "-o", exe, os.path.join(tmp, "driver.cxx")],
                           check=True)
            run = subprocess.run([exe], capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stdout)

    def test_set_context_wiring(self):
        tabctrl = added(PATCH, "vcl/source/control/tabctrl.cxx")
        # LibreOfficeKit keeps the upstream path
        self.assertIn("const bool bHstKeepTab = !comphelper::LibreOfficeKit::isActive();", tabctrl)
        self.assertIn("m_nHstKeepPage = hst::ribbon::keepTabBefore(m_nHstKeepPage, mnCurPageId, bContextual);",
                      tabctrl)
        self.assertIn("bHstOpened = bHstOpened || !pPage->HasContext(vcl::EnumContext::Context::Any);", tabctrl)
        self.assertIn("pKept && pKept->HasContext(eContext) && pKept->IsEnabled(), bHstOpened);", tabctrl)
        # the remembered page is forgotten by an idle task, stopped with the control
        self.assertIn("m_aHstKeepIdle.SetPriority(TaskPriority::DEFAULT_IDLE);", tabctrl)
        self.assertIn("    m_nHstKeepPage = 0;", tabctrl)
        self.assertIn("    m_aHstKeepIdle.Stop();", tabctrl)
        header = added(PATCH, "include/vcl/tabctrl.hxx")
        self.assertIn("Idle m_aHstKeepIdle;", header)
        self.assertIn("DECL_DLLPRIVATE_LINK(HstKeepTabExpired, Timer*, void);", header)

    def test_keep_step_runs_last_in_set_context(self):
        # after the fall back to the default tab, just before the final Resize() of SetContext
        hunks = "\n".join(sections(PATCH)["vcl/source/control/tabctrl.cxx"])
        self.assertIn("+        if (nRestore)\n+            SetCurPageId(nRestore);\n+    }\n+\n"
                      "     // tdf#152908 Tabbed compact toolbar does not repaint itself when tabs getting removed",
                      hunks)


if __name__ == "__main__":
    unittest.main()
