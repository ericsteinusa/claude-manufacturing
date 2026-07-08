"""Django management command — bulk inventory + price sync to storefronts.

Usage:
    python manage.py sync_ecommerce

Scheduled via Windows Task Scheduler or cron (real-time push is out of
scope in this environment — see manufacturing/ecommerce_core.py's module
docstring; this batch command is the schedulable stand-in):

    # cron (Linux): run every 15 minutes
    */15 * * * * cd /path/to/project && python manage.py sync_ecommerce

    # Task Scheduler (Windows): action = python manage.py sync_ecommerce
    # Trigger: every 15 minutes

For every active storefront_connection, pushes the current on-hand qty
and price-list price for every product mapped in that connection's
storefront_item_xref via ecommerce_core.push_inventory_level /
push_price_update. Each push is config-gated: if the connection has no
sync_endpoint_url configured, the attempt is logged as 'queued' rather
than faked as delivered.
"""

from django.core.management.base import BaseCommand

from manufacturing.db_pg import get_db_connection
from manufacturing import ecommerce_core


class Command(BaseCommand):
    help = 'Bulk-sync inventory levels and prices to all active storefront connections.'

    def handle(self, *args, **options):
        conn = get_db_connection()
        try:
            ecommerce_core.ensure_ecommerce_tables(conn)
            conn.commit()

            counts = {'success': 0, 'queued': 0, 'failed': 0}
            connections = [c for c in ecommerce_core.list_connections(conn) if c['is_active']]
            for connection in connections:
                xrefs = ecommerce_core.list_item_xrefs(conn, connection['id'])
                for xref in xrefs:
                    for result in (
                        ecommerce_core.push_inventory_level(
                            conn, connection['id'], xref['product_id'], created_by='sync_ecommerce'),
                        ecommerce_core.push_price_update(
                            conn, connection['id'], xref['product_id'], created_by='sync_ecommerce'),
                    ):
                        counts[result['status']] = counts.get(result['status'], 0) + 1
            conn.commit()
        finally:
            conn.close()

        self.stdout.write(
            f"e-Commerce sync complete: {counts['success']} sent, "
            f"{counts['queued']} queued (no endpoint), {counts['failed']} failed."
        )
