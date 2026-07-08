"""Guards the invariant manufacturing.views.generic_menu relies on.

generic_menu resolves every non-submenu leaf with a bare
``WEB_LEAF_URLS[(dept, key)]`` subscript (no fallback) — see
manufacturing/views/__init__.py. A menus.MENU_TREE leaf added or renamed
without a matching WEB_LEAF_URLS entry would raise an uncaught KeyError and
500 the entire department menu page for every user. This test catches that
at collection time instead of in production.

manufacturing.views imports django.shortcuts/django.urls, which need
DJANGO_SETTINGS_MODULE set but NOT a populated app registry — deliberately
skip django.setup() here, since manufacturing.apps.ManufacturingConfig.ready()
calls init_schema(), which opens a real Postgres connection and would fail
in any environment without a live DB (e.g. CI). WEB_LEAF_URLS is a plain
module-level dict, so a bare import is all this test needs.
"""

import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'manufacture.settings')

from manufacturing import menus, views  # noqa: E402


def _iter_leaves(dept, node):
    for key, _label, target in node['items']:
        if isinstance(target, dict):
            yield from _iter_leaves(dept, target)
        else:
            yield (dept, key)


def test_every_menu_tree_leaf_has_a_web_leaf_url():
    missing = [
        leaf
        for dept, node in menus.MENU_TREE.items()
        for leaf in _iter_leaves(dept, node)
        if leaf not in views.WEB_LEAF_URLS
    ]
    assert not missing, (
        f"{len(missing)} menu leaf(ves) have no views.WEB_LEAF_URLS entry: "
        f"{missing} — generic_menu's WEB_LEAF_URLS[(dept, key)] lookup has "
        f"no fallback and will KeyError/500 the whole department page"
    )
