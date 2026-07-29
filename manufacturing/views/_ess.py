"""Views: Employee Self-Service (ESS) Portal (P2-G).

Every view here is scoped to the logged-in employee's own records —
gated by login_required (any authenticated user, no dept/role check, since
employees belong to every department) plus an explicit ownership check on
every detail view (compare the record's people_id to the caller's own).
Time-off request/history and clock in/out were already self-scoped before
this module (time_off_list/new/detail, time_clock_status/hours) — ESS
just links to those directly rather than duplicating them.
"""

from datetime import date

from django.shortcuts import render, redirect

from ..db_pg import get_db_connection
from ..auth_decorators import login_required
from ..log_utils import get_logger

from ..personnel_core import (
    get_person_by_email, get_person,
    ensure_contact_columns, get_own_contact_info, update_own_contact_info,
    ensure_time_off_balance_table, get_time_off_balance,
    list_time_off_requests,
    init_review_table, list_reviews, get_review,
    init_training_table, list_trainings, get_training,
)
from ..payroll_core import (
    list_pay_stubs_for_employee, get_pay_stub, get_stub_deductions,
    get_ytd, SS_RATE, MEDICARE_RATE,
)

log = get_logger(__name__)


def _ess_ctx(request, **extra):
    ctx = {'email': request.session.get('user_email', '')}
    ctx.update(extra)
    return ctx


def _my_people_id(request, conn):
    person = get_person_by_email(conn, request.session.get('user_email', ''))
    return person['id'] if person else None


@login_required
def ess_home(request):
    conn = get_db_connection()
    try:
        pid = _my_people_id(request, conn)
        if not pid:
            return redirect('dashboard')
        ensure_time_off_balance_table(conn)
        init_review_table(conn)
        init_training_table(conn)
        conn.commit()

        person = get_person(conn, pid)
        balance = get_time_off_balance(conn, pid)
        stubs = list_pay_stubs_for_employee(conn, pid)
        reviews = list_reviews(conn, people_id=pid)
        trainings = list_trainings(conn, people_id=pid)
        time_off_requests = list_time_off_requests(conn, people_id=pid)
    finally:
        conn.close()

    return render(request, 'ess_home.html', _ess_ctx(
        request, person=person, balance=balance,
        latest_stub=stubs[0] if stubs else None,
        pending_reviews=[r for r in reviews if r['status'] in ('Scheduled', 'In Progress')],
        upcoming_trainings=[t for t in trainings if t['status'] in ('Scheduled', 'In Progress')],
        open_time_off=[r for r in time_off_requests if r['status'] == 'pending'],
    ))


@login_required
def ess_pay_stubs(request):
    conn = get_db_connection()
    try:
        pid = _my_people_id(request, conn)
        if not pid:
            return redirect('dashboard')
        stubs = list_pay_stubs_for_employee(conn, pid)
    finally:
        conn.close()
    return render(request, 'ess_pay_stubs.html', _ess_ctx(request, stubs=stubs))


@login_required
def ess_pay_stub_detail(request, entry_id):
    conn = get_db_connection()
    try:
        pid = _my_people_id(request, conn)
        stub = get_pay_stub(conn, entry_id)
        if not stub or not pid or stub.get('people_id') != pid:
            return redirect('ess_pay_stubs')
        deds = get_stub_deductions(conn, entry_id)
    finally:
        conn.close()

    pre_tax = [d for d in deds if d.get('is_pre_tax')]
    post_tax = [d for d in deds if not d.get('is_pre_tax')]
    total_tax = (
        (stub.get('federal_tax') or 0) + (stub.get('state_tax') or 0)
        + (stub.get('social_security') or 0) + (stub.get('medicare') or 0)
    )
    return render(request, 'ess_pay_stub_detail.html', _ess_ctx(
        request, stub=stub, pre_tax=pre_tax, post_tax=post_tax,
        total_tax=total_tax, ss_rate=SS_RATE, medicare_rate=MEDICARE_RATE,
    ))


@login_required
def ess_ytd(request):
    cur_year = date.today().year
    try:
        year = int(request.GET.get('year', cur_year))
    except ValueError:
        year = cur_year

    conn = get_db_connection()
    try:
        pid = _my_people_id(request, conn)
        if not pid:
            return redirect('dashboard')
        rows = get_ytd(conn, year, people_id=pid)
    finally:
        conn.close()

    return render(request, 'ess_ytd.html', _ess_ctx(
        request, ytd=rows[0] if rows else None, year=year,
        year_options=[cur_year, cur_year - 1, cur_year - 2, cur_year - 3],
    ))


@login_required
def ess_time_off(request):
    conn = get_db_connection()
    try:
        pid = _my_people_id(request, conn)
        if not pid:
            return redirect('dashboard')
        ensure_time_off_balance_table(conn)
        conn.commit()
        balance = get_time_off_balance(conn, pid)
        my_requests = list_time_off_requests(conn, people_id=pid)
    finally:
        conn.close()

    return render(request, 'ess_time_off.html', _ess_ctx(
        request, balance=balance, requests=my_requests,
    ))


@login_required
def ess_reviews(request):
    conn = get_db_connection()
    try:
        pid = _my_people_id(request, conn)
        if not pid:
            return redirect('dashboard')
        init_review_table(conn)
        conn.commit()
        reviews = list_reviews(conn, people_id=pid)
    finally:
        conn.close()
    return render(request, 'ess_reviews.html', _ess_ctx(request, reviews=reviews))


@login_required
def ess_review_detail(request, review_id):
    conn = get_db_connection()
    try:
        pid = _my_people_id(request, conn)
        init_review_table(conn)
        review = get_review(conn, review_id)
        if not review or not pid or review.get('people_id') != pid:
            return redirect('ess_reviews')
    finally:
        conn.close()
    return render(request, 'ess_review_detail.html', _ess_ctx(request, review=review))


@login_required
def ess_trainings(request):
    conn = get_db_connection()
    try:
        pid = _my_people_id(request, conn)
        if not pid:
            return redirect('dashboard')
        init_training_table(conn)
        conn.commit()
        trainings = list_trainings(conn, people_id=pid)
    finally:
        conn.close()
    return render(request, 'ess_trainings.html', _ess_ctx(request, trainings=trainings))


@login_required
def ess_training_detail(request, training_id):
    conn = get_db_connection()
    try:
        pid = _my_people_id(request, conn)
        init_training_table(conn)
        training = get_training(conn, training_id)
        if not training or not pid or training.get('people_id') != pid:
            return redirect('ess_trainings')
    finally:
        conn.close()
    return render(request, 'ess_training_detail.html', _ess_ctx(request, training=training))


@login_required
def ess_profile(request):
    conn = get_db_connection()
    error = success = None
    try:
        pid = _my_people_id(request, conn)
        if not pid:
            return redirect('dashboard')
        ensure_contact_columns(conn)
        conn.commit()

        if request.method == 'POST':
            try:
                update_own_contact_info(
                    conn, pid,
                    address=request.POST.get('address', '').strip(),
                    city=request.POST.get('city', '').strip(),
                    state=request.POST.get('state', '').strip(),
                    zip_code=request.POST.get('zip_code', '').strip(),
                    phone=request.POST.get('phone', '').strip(),
                    emergency_contact_name=request.POST.get('emergency_contact_name', '').strip(),
                    emergency_contact_phone=request.POST.get('emergency_contact_phone', '').strip(),
                    emergency_contact_relationship=request.POST.get(
                        'emergency_contact_relationship', '').strip(),
                )
                conn.commit()
                success = 'Contact info updated.'
            except Exception as exc:
                conn.rollback()
                error = str(exc)

        info = get_own_contact_info(conn, pid)
    finally:
        conn.close()

    return render(request, 'ess_profile.html', _ess_ctx(
        request, info=info, error=error, success=success,
    ))
