"""Views: outbound webhook subscription admin.

Cross-departmental system configuration (subscriptions fire on WO/PO/SO
status changes and NCR creation across every department), so this is gated
like the other Admin-sidebar pages (User Roles, Approval Rules) rather than
a single department — full-access roles only.
"""

from django.shortcuts import render, redirect

from ..db_pg import get_db_connection
from ..log_utils import get_logger
from ..accounts import _ROLE_ADMIN_ROLES
from ..webhook_core import (
    EVENT_TYPES,
    ensure_webhook_tables,
    create_subscription,
    list_subscriptions,
    get_subscription,
    update_subscription,
    delete_subscription,
    list_deliveries,
)

log = get_logger(__name__)


def _is_admin(request) -> bool:
    return bool(request.session.get('user_email')) and (
        request.session.get('user_role') in _ROLE_ADMIN_ROLES)


def _wh_ctx(request, **extra):
    ctx = {
        'email': request.session.get('user_email', ''),
        'user_role': request.session.get('user_role', ''),
        'full_access': request.session.get('user_full_access', False),
        'event_types': EVENT_TYPES,
    }
    ctx.update(extra)
    return ctx


def webhook_list(request):
    if not request.session.get('user_email'):
        return redirect('home')
    if not _is_admin(request):
        return redirect('dashboard')

    event_type = request.GET.get('event_type', '').strip()
    conn = get_db_connection()
    try:
        ensure_webhook_tables(conn)
        subscriptions = list_subscriptions(conn, event_type=event_type or None)
    finally:
        conn.close()
    return render(request, 'webhook_list.html', _wh_ctx(
        request, subscriptions=subscriptions, event_type=event_type,
    ))


def webhook_new(request):
    if not request.session.get('user_email'):
        return redirect('home')
    if not _is_admin(request):
        return redirect('dashboard')

    error = None
    conn = get_db_connection()
    try:
        ensure_webhook_tables(conn)
        if request.method == 'POST':
            event_type = request.POST.get('event_type', '').strip()
            target_url = request.POST.get('target_url', '').strip()
            try:
                sub_id = create_subscription(
                    conn, event_type, target_url,
                    secret=request.POST.get('secret', '').strip(),
                    created_by=request.session.get('user_email', ''),
                )
                conn.commit()
                return redirect('webhook_edit', subscription_id=sub_id)
            except (ValueError, TypeError) as exc:
                conn.rollback()
                error = str(exc)
    finally:
        conn.close()
    return render(request, 'webhook_new.html', _wh_ctx(request, error=error))


def webhook_edit(request, subscription_id):
    if not request.session.get('user_email'):
        return redirect('home')
    if not _is_admin(request):
        return redirect('dashboard')

    error = success = None
    conn = get_db_connection()
    try:
        ensure_webhook_tables(conn)
        subscription = get_subscription(conn, subscription_id)
        if not subscription:
            return redirect('webhook_list')

        if request.method == 'POST':
            action = request.POST.get('action', '')
            try:
                if action == 'update':
                    update_subscription(
                        conn, subscription_id,
                        event_type=request.POST.get('event_type', '').strip(),
                        target_url=request.POST.get('target_url', '').strip(),
                        secret=request.POST.get('secret', '').strip(),
                    )
                    conn.commit()
                    success = 'Subscription updated.'
                elif action == 'toggle_active':
                    update_subscription(
                        conn, subscription_id, is_active=not subscription['is_active'])
                    conn.commit()
                    success = ('Subscription deactivated.' if subscription['is_active']
                              else 'Subscription activated.')
                elif action == 'delete':
                    delete_subscription(conn, subscription_id)
                    conn.commit()
                    return redirect('webhook_list')
            except Exception as exc:
                conn.rollback()
                error = str(exc)
            subscription = get_subscription(conn, subscription_id)

        deliveries = list_deliveries(conn, subscription_id=subscription_id, limit=20)
    finally:
        conn.close()

    return render(request, 'webhook_edit.html', _wh_ctx(
        request, subscription=subscription, deliveries=deliveries,
        error=error, success=success,
    ))
