# Desktop App Removal Plan

**Status:** In progress — deletions and code/doc edits done, verification next
**Decision:** Retire the PyQt6 desktop application entirely. The Django
web UI becomes the only UI. `python manage.py runserver` becomes the
one and only way to run the application.

This document is the working checklist for that migration — check items
off as they're completed. It supersedes PR #396
(`feature/desktop-web-shell`, embedding the web UI in a QWebEngineView
desktop shell), which becomes pointless with no desktop app left to
wrap and should be closed unmerged once this work is underway.

---

## Context / why this is lower-risk than it looks

- **The web UI already has 100% menu coverage.** `menus.py`'s
  `MENU_TREE` has 552 unique `(dept, leaf_key)` leaves; `views/
  __init__.py`'s `WEB_LEAF_URLS` dict (lines 241–901) has 599 entries.
  Cross-referenced programmatically: **zero tree leaves lack a web
  page.** The 47-entry surplus is stale dead entries from past tree
  restructuring (harmless, out of scope here).
- Because of that, `generic_menu` (`views/__init__.py:996`) never
  actually emits a `/run/.../` link for any live leaf today —
  `views.run_script`'s PyQt6-subprocess-launch fallback is **already
  unreachable, dead code**. Deleting the desktop screens it would have
  launched breaks nothing currently reachable through the web UI.
  (CLAUDE.md's "Most leaves are still desktop-only" line is stale and
  gets corrected as part of this change.)
- **All business logic already lives outside the Qt layer.** Every
  `*_core.py` module is Qt-free by design and is imported by the web
  `views/` — **none of them are touched**. This removal is purely
  deleting the PyQt6 UI layer and its supporting scaffolding/assets.
- **No test breakage risk.** None of the 62 pytest-collected `tests/
  test_*.py` files import PyQt6 or any desktop screen module (confirmed
  by grep). The only Qt-based files under `tests/` (`qt_one_window.py`,
  `qt_tabs.py`, `qt_fixed_buttons.py`) are manual smoke scripts pytest
  never collects.
- **`python-barcode`/`reportlab` stay** — confirmed shared: `barcode_
  core.py` backs both the desktop `qt_barcode.py` (missed by the
  original PyQt6 file sweep below, left as unreferenced dead code
  until deleted separately in PR #74) and five live web views
  (`label_wo`/`label_part`/`label_po`/`label_receiving`/
  `label_asset` in `views/_barcode.py`, routed in `urls.py:419-423`).
  Only `PyQt6`/`PyQt6-WebEngine` are desktop-only and get dropped from
  `requirements.txt`.

---

## Checklist

### 1. New branch
- [x] Create `feature/drop-desktop-app` off latest `main` (not built on
      `feature/desktop-web-shell` — that work is being abandoned).

### 2. Delete PyQt6-importing `.py` files (122 files)
- [x] Shared desktop infra: `login_app.py`, `Company_main_menu.py`,
      `qt_theme.py`, `button_nav.py`, `dept_menu_widget.py`,
      `web_shell.py`, `print_utils.py`, `connect_db.py`, `Splash.py`,
      `password.py`, `registration_form.py`, `registration.py`,
      `New_password_update.py` (13 files — `web_shell.py` never existed
      on `main`, so only 12 were actually present; total is 121 files)
- [x] Department main-menu files: `*_Main_menu.py` / `*_mgr_menu.py`
      across every department subpackage, including stale `_old`
      variants (42 files)
- [x] Individual feature-screen files across every department
      subpackage, e.g. `production/work_orders.py`, `sales/
      sales_orders.py`, `accounting/Accounts_payable.py` (67 files)
- [x] Bonus: `manufacturing/launch_utils.py` and
      `tests/test_launch_utils.py` — not PyQt6-importing, but its only
      callers were the deleted desktop menu files, so it became dead
      code as a direct result of this deletion (not in the original
      count; found during cleanup).

### 3. Delete entry-point / launcher scripts
- [x] `run.py` (gitignored — deleted from disk only, no git diff)
- [x] `launch_app.bat` (gitignored — deleted from disk only)
- [x] `run_login_test.py` (gitignored — deleted from disk only)
- [x] `run_login_test.bat` (gitignored — deleted from disk only)
- [x] `setup_qt_fonts.py`

### 4. Delete dead Qt Designer artifacts
(Already confirmed unused — `requirements.txt`'s own comment says "no
hand-written module imports them".)
- [x] 44 `.ui` files (gitignored — deleted from disk only, no git diff)
- [x] 4 `.qrc` files
- [x] 3 generated `*_ui.py` files (these import PyQt6 directly, so
      they were already caught by section 2's git rm)
- [x] 4 generated `*_rc.py` files (gitignored — deleted from disk
      only, no git diff)
- [x] 24 department icon/wallpaper images (`.png`/`.jpg`) only
      referenced by those `.ui` files

### 5. Delete manual Qt smoke scripts
- [x] `tests/qt_one_window.py`
- [x] `tests/qt_tabs.py`
- [x] `tests/qt_fixed_buttons.py`

### 6. Clean up `requirements.txt`
- [x] Drop `PyQt6==6.11.0` (no `PyQt6-WebEngine` line existed on
      `main` — that was only added on the abandoned
      `feature/desktop-web-shell` branch) and the explanatory comment
      block
- [x] Keep everything else, including `python-barcode`/`reportlab`
      (shared with web label-printing views)

### 7. Clean up `manufacturing/views/__init__.py`
- [x] Remove `run_script` (now provably dead — no reachable caller,
      and its target modules are gone)
- [x] Simplify `generic_menu`'s leaf-resolution branch to use
      `WEB_LEAF_URLS` directly (removed the `else: url = '/run/...'`
      fallback); also dropped the now-unused `os`/`sys`/`subprocess`
      imports that only `run_script` needed

### 8. Clean up `manufacturing/urls.py`
- [x] Remove the `run/<str:dept>/<path:subpath>/` route

### 9. Update docs
- [x] `README.md` — replaced the PyQt6-desktop-focused "Running the
      Application"/"Project Structure" sections with `python manage.py
      runserver` instructions; replaced the per-department desktop
      tab/widget deep-dives (which documented internals of now-deleted
      files) with a pointer to the web menu tree
- [x] `CLAUDE.md` — rewrote the opening line (no longer "PyQt6 desktop
      app... plus a Django web UI" — just a Django app); removed the
      "Testing & CI" PyQt6/libEGL and Windows-offscreen-fonts notes;
      rewrote the "Web UI (Django) & menu routing" section to drop the
      stale "most leaves are still desktop-only"/`WEB_LEAF_URLS`-as-
      exception framing; removed the deleted `qt_theme.py`/
      `button_nav.py`/`dept_menu_widget.py`/`launch_utils.py` from the
      directory-structure listing; fixed a stale comment in
      `menus.py` referencing deleted `login_app.SessionWindow`/
      `Company_main_menu.DEPARTMENTS`
- [x] `manufacturing/COMPETITIVE_GAP_ANALYSIS.md` — left as-is (a
      competitive-feature roadmap doc, not architecture documentation)

### 10. Verify
- [x] `pytest -q` (full suite — 1954 passed, no failures)
- [x] `ruff check .` — all checks passed
- [x] `python manage.py check` — no issues
- [x] Grep the whole repo post-deletion for `PyQt6`/`QtWidgets`/
      `QtCore` to confirm zero real remaining references — only
      harmless prose mentions remain in a handful of `*_core.py`
      docstrings/comments ("this module has no PyQt6 dependency") and
      one commented-out line in `payroll/update_users.py`; none
      reference a specific file
- [x] Start `python manage.py runserver` for real and click through
      the web menu tree for a couple of departments to confirm every
      leaf still resolves to a real page — logged in as a sample user
      and hit `/dashboard/`, `/dept/production/`, `/dept/accounting/`,
      nested submenus, `/po/`, `/customers/new/`, `/bom/`,
      `/inventory/`, `/it/`, `/legal/`, `/gl/`: all 200, zero
      tracebacks in the server log, zero stray `/run/` links in the
      rendered menu HTML
- [x] `git diff --stat` — 211 files changed: 197 deletions (the
      planned files, plus `launch_utils.py` + its test, and
      `customers/customer_entry.py` — all found to be dead fallout
      from the deletion, not in the original count) and 14
      modifications (`requirements.txt`, `views/__init__.py`,
      `urls.py`, `README.md`, `CLAUDE.md`, `menus.py`, and — beyond the
      plan's original prediction — 7 `*_core.py` files, each a
      docstring/comment-only fix removing stale "kept separate from
      X.py (which imports PyQt6)" references to files this same change
      deletes; verified no logic lines changed in any of them)

### 11. Ship
- [ ] Push `feature/drop-desktop-app`, open PR
- [ ] Close PR #396 (`feature/desktop-web-shell`) with a comment
      explaining it's superseded by this change
