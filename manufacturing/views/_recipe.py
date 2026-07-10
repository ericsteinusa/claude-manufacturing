"""Views: Recipe / Formula Management."""

from django.shortcuts import render, redirect

from ..db_pg import get_db_connection
from ..auth_decorators import dept_required
from ..log_utils import get_logger
from ..accounts import READ_ONLY_ROLES

from ..recipe_core import (
    ensure_recipe_tables, list_recipes, get_recipe, create_recipe,
    add_ingredient, activate_recipe, scale_recipe, release_batch_wo,
    RECIPE_STATUSES,
)
from ..bom_web_core import list_products
from ..work_orders_core import next_wo_number

log = get_logger(__name__)

_RECIPE_DEPT_KEYS = {'production', 'engineering'}


def _recipe_ctx(request, **extra):
    ctx = {
        'email': request.session.get('user_email', ''),
        'user_role': request.session.get('user_role', ''),
        'full_access': request.session.get('user_full_access', False),
        'can_edit': request.session.get('user_role') not in READ_ONLY_ROLES,
        'recipe_statuses': RECIPE_STATUSES,
    }
    ctx.update(extra)
    return ctx


@dept_required(_RECIPE_DEPT_KEYS)
def recipe_list(request):
    conn = get_db_connection()
    try:
        ensure_recipe_tables(conn)
        recipes = list_recipes(conn, status=request.GET.get('status') or None)
    finally:
        conn.close()
    return render(request, 'recipe_list.html', _recipe_ctx(
        request, recipes=recipes, status=request.GET.get('status', ''),
    ))


@dept_required(_RECIPE_DEPT_KEYS, write_redirect='recipe_list')
def recipe_new(request):
    conn = get_db_connection()
    error = None
    try:
        ensure_recipe_tables(conn)
        products = list_products(conn)
        if request.method == 'POST':
            try:
                recipe_id = create_recipe(
                    conn, int(request.POST['product_id']),
                    request.POST.get('name', '').strip(),
                    batch_size=float(request.POST.get('batch_size') or 0),
                    batch_uom=request.POST.get('batch_uom', 'kg').strip() or 'kg',
                    yield_pct=float(request.POST.get('yield_pct') or 100.0),
                    revision=request.POST.get('revision', 'A').strip() or 'A',
                    created_by=request.session.get('user_email', ''),
                )
                conn.commit()
                return redirect('recipe_detail', recipe_id=recipe_id)
            except (ValueError, TypeError) as exc:
                conn.rollback()
                error = str(exc)
    finally:
        conn.close()
    return render(request, 'recipe_new.html', _recipe_ctx(
        request, products=products, error=error,
    ))


@dept_required(_RECIPE_DEPT_KEYS, write_redirect='recipe_list')
def recipe_detail(request, recipe_id):
    conn = get_db_connection()
    error = success = None
    scaled = None
    try:
        ensure_recipe_tables(conn)
        recipe = get_recipe(conn, recipe_id)
        if not recipe:
            return redirect('recipe_list')
        products = list_products(conn)

        if request.method == 'POST':
            action = request.POST.get('action', '')
            try:
                if action == 'add_ingredient':
                    add_ingredient(
                        conn, recipe_id, int(request.POST['component_id']),
                        qty_per_batch=float(request.POST.get('qty_per_batch') or 0),
                        uom=request.POST.get('uom', 'kg').strip() or 'kg',
                        sequence=int(request.POST.get('sequence') or 0),
                    )
                    conn.commit()
                    success = 'Ingredient added.'
                elif action == 'activate':
                    activate_recipe(conn, recipe_id)
                    conn.commit()
                    success = 'Recipe activated.'
                elif action == 'scale':
                    scaled = scale_recipe(conn, recipe_id, float(request.POST.get('target_qty') or 0))
                elif action == 'release':
                    wo_number = next_wo_number(conn)
                    wo_id = release_batch_wo(
                        conn, recipe_id, wo_number,
                        target_qty=float(request.POST.get('target_qty') or 0),
                        created_by=request.session.get('user_email', ''),
                    )
                    conn.commit()
                    return redirect('wo_detail', wo_id=wo_id)
            except (ValueError, TypeError) as exc:
                conn.rollback()
                error = str(exc)
            recipe = get_recipe(conn, recipe_id)
    finally:
        conn.close()

    return render(request, 'recipe_detail.html', _recipe_ctx(
        request, recipe=recipe, products=products, scaled=scaled,
        error=error, success=success,
    ))
