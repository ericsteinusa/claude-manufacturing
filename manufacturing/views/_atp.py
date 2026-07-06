"""Views: Available-to-Promise (ATP) inquiry (P2-B)."""

from datetime import date

from django.shortcuts import render

from ..db_pg import get_db_connection
from ..auth_decorators import dept_required
from ..log_utils import get_logger
from ..accounts import READ_ONLY_ROLES

from ..atp_core import get_atp
from ..sales_orders_core import load_products

log = get_logger(__name__)


def _atp_ctx(request, **extra):
    ctx = {
        'email': request.session.get('user_email', ''),
        'user_role': request.session.get('user_role', ''),
        'full_access': request.session.get('user_full_access', False),
        'can_edit': request.session.get('user_role') not in READ_ONLY_ROLES,
    }
    ctx.update(extra)
    return ctx


@dept_required('sales')
def atp_inquiry(request):
    """GET renders an empty form; POST computes ATP and re-renders the same
    template with `result` populated — no separate results URL (matches
    this app's plain-form-POST convention). Read-only, so no
    write_redirect — Auditors can use it too."""
    conn = get_db_connection()
    try:
        products = load_products(conn)
        form = {
            'product_id': '', 'qty': '1',
            'requested_date': date.today().isoformat(),
        }
        result = error = None
        if request.method == 'POST':
            form['product_id'] = request.POST.get('product_id', '')
            form['qty'] = request.POST.get('qty', '1')
            form['requested_date'] = (
                request.POST.get('requested_date') or date.today().isoformat())
            try:
                product_id = int(form['product_id'])
                qty = float(form['qty'])
                if qty <= 0:
                    raise ValueError
            except (TypeError, ValueError):
                error = 'Select a product and enter a quantity greater than 0.'
            else:
                result = get_atp(conn, product_id, qty, form['requested_date'])
                result['product_name'] = next(
                    (p['product_name'] for p in products if p['id'] == product_id), '')
    finally:
        conn.close()
    return render(request, 'atp_inquiry.html', _atp_ctx(
        request, products=products, form=form, result=result, error=error))
