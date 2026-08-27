"""Views: Document Control module (P2-F)."""

import mimetypes
import os

from django.conf import settings
from django.http import FileResponse, Http404
from django.shortcuts import render, redirect
from django.utils.text import get_valid_filename

from ..db_pg import get_db_connection
from ..auth_decorators import dept_required
from ..log_utils import get_logger
from ..accounts import READ_ONLY_ROLES, _verify_login

from ..document_control_core import (
    ensure_document_tables, list_documents, get_document, create_document,
    attach_file, get_revisions, create_revision, submit_for_review,
    decide_document, mark_superseded, mark_obsolete,
    get_links, add_link, remove_link,
    DOC_TYPES, STATUSES, LINK_TYPES,
)
from ..approval_workflow_core import get_entity_approval_status
from ..sales_orders_core import load_products
from ..sampling_plan_core import list_sampling_plans
from ..maintenance_core import list_equipment
from ..routing_core import list_workcenters

log = get_logger(__name__)

_DOC_DEPT_KEYS = {'quality_assurance', 'engineering'}

# Sub-directory of MEDIA_ROOT where uploaded document files are stored.
_UPLOAD_SUBDIR = 'documents'


def _doc_ctx(request, **extra):
    ctx = {
        'email': request.session.get('user_email', ''),
        'user_role': request.session.get('user_role', ''),
        'full_access': request.session.get('user_full_access', False),
        'can_edit': request.session.get('user_role') not in READ_ONLY_ROLES,
        'doc_types': DOC_TYPES,
        'statuses': STATUSES,
        'link_types': LINK_TYPES,
    }
    ctx.update(extra)
    return ctx


def _save_upload(doc_number, revision, upload):
    """Write an uploaded file under MEDIA_ROOT/documents/<doc_number>/<rev>/
    and return (relative_path, original_filename). Only view-layer code
    touches the filesystem — document_control_core stays Qt-free and
    disk-free so its tests never write real files."""
    safe_name = get_valid_filename(upload.name)
    rel_dir = os.path.join(_UPLOAD_SUBDIR, doc_number, revision)
    abs_dir = os.path.join(settings.MEDIA_ROOT, rel_dir)
    os.makedirs(abs_dir, exist_ok=True)
    rel_path = os.path.join(rel_dir, safe_name)
    abs_path = os.path.join(settings.MEDIA_ROOT, rel_path)
    with open(abs_path, 'wb') as fh:
        for chunk in upload.chunks():
            fh.write(chunk)
    return rel_path.replace('\\', '/'), upload.name


@dept_required(_DOC_DEPT_KEYS)
def document_list(request):
    status = request.GET.get('status') or None
    doc_type = request.GET.get('doc_type') or None
    search = request.GET.get('q') or None
    conn = get_db_connection()
    try:
        ensure_document_tables(conn)
        documents = list_documents(conn, status=status, doc_type=doc_type, search=search)
    finally:
        conn.close()
    return render(request, 'document_list.html', _doc_ctx(
        request, documents=documents, status=status, doc_type=doc_type, search=search or '',
    ))


@dept_required(_DOC_DEPT_KEYS, write_redirect='document_list')
def document_new(request):
    conn = get_db_connection()
    error = None
    try:
        ensure_document_tables(conn)
        if request.method == 'POST':
            title = request.POST.get('title', '').strip()
            doc_type = request.POST.get('doc_type', 'SOP')
            try:
                doc_id = create_document(
                    conn, title, doc_type,
                    owner=request.POST.get('owner', '').strip(),
                    dept_key=request.session.get('user_dept_key', ''),
                    notes=request.POST.get('notes', '').strip(),
                    created_by=request.session.get('user_email', ''),
                )
                conn.commit()
                return redirect('document_detail', doc_id=doc_id)
            except ValueError as exc:
                conn.rollback()
                error = str(exc)
    finally:
        conn.close()
    return render(request, 'document_new.html', _doc_ctx(request, error=error))


@dept_required(_DOC_DEPT_KEYS, write_redirect='document_list')
def document_detail(request, doc_id):
    conn = get_db_connection()
    error = success = None
    try:
        ensure_document_tables(conn)
        doc = get_document(conn, doc_id)
        if not doc:
            return redirect('document_list')

        if request.method == 'POST':
            action = request.POST.get('action', '')
            by = request.session.get('user_email', '')
            try:
                if action == 'submit_review':
                    submit_for_review(conn, doc_id, requested_by=by)
                elif action == 'decide':
                    signature_meaning = request.POST.get('signature_meaning', '').strip()
                    password = request.POST.get('password', '')
                    if not signature_meaning:
                        raise ValueError(
                            'A meaning of signature is required to record this decision.')
                    if not _verify_login(by, password):
                        raise ValueError(
                            'Incorrect password — signature not recorded.')
                    decide_document(
                        conn, doc_id, int(request.POST.get('step_id')),
                        request.POST.get('decision', ''), by,
                        notes=request.POST.get('notes', '').strip(),
                        signature_meaning=signature_meaning,
                    )
                elif action == 'upload':
                    upload = request.FILES.get('file')
                    if upload:
                        rel_path, orig_name = _save_upload(
                            doc['doc_number'], doc['current_revision'], upload)
                        attach_file(conn, doc_id, rel_path, orig_name)
                elif action == 'revise':
                    upload = request.FILES.get('file')
                    rel_path = orig_name = ''
                    new_rev = create_revision(
                        conn, doc_id, request.POST.get('change_description', '').strip(),
                        by,
                    )
                    if upload:
                        rel_path, orig_name = _save_upload(doc['doc_number'], new_rev, upload)
                        attach_file(conn, doc_id, rel_path, orig_name)
                elif action == 'supersede':
                    mark_superseded(conn, doc_id)
                elif action == 'obsolete':
                    mark_obsolete(conn, doc_id)
                elif action == 'add_link':
                    linked_type = request.POST.get('linked_type', '')
                    linked_id_raw = request.POST.get('linked_id', '')
                    if linked_type and linked_id_raw:
                        add_link(conn, doc_id, linked_type, int(linked_id_raw), created_by=by)
                elif action == 'remove_link':
                    remove_link(conn, int(request.POST.get('link_id')))
                conn.commit()
                success = 'Saved.'
                doc = get_document(conn, doc_id)
            except (ValueError, TypeError) as exc:
                conn.rollback()
                error = str(exc)

        approval = get_entity_approval_status(conn, 'document', doc['current_revision_id'])
        revisions = get_revisions(conn, doc_id)
        links = get_links(conn, doc_id)
        link_products = load_products(conn)
        link_plans = list_sampling_plans(conn)
        link_equipment = list_equipment(conn)
        link_workcenters = list_workcenters(conn)
    finally:
        conn.close()

    user_role = request.session.get('user_role', '')
    full_access = request.session.get('user_full_access', False)
    pending_step = next(
        (s for s in approval['steps']
         if s['status'] == 'pending'
         and (full_access or s['approver_role'] == user_role)),
        None,
    )

    return render(request, 'document_detail.html', _doc_ctx(
        request, doc=doc, approval=approval, pending_step=pending_step,
        revisions=revisions, links=links,
        link_products=link_products, link_plans=link_plans,
        link_equipment=link_equipment, link_workcenters=link_workcenters,
        error=error, success=success,
    ))


@dept_required(_DOC_DEPT_KEYS)
def document_download(request, doc_id):
    conn = get_db_connection()
    try:
        ensure_document_tables(conn)
        doc = get_document(conn, doc_id)
    finally:
        conn.close()
    if not doc or not doc['file_path']:
        raise Http404('No file attached to this document')
    abs_path = os.path.join(settings.MEDIA_ROOT, doc['file_path'])
    if not os.path.isfile(abs_path):
        raise Http404('File not found on disk')
    content_type, _ = mimetypes.guess_type(doc['file_name'])
    response = FileResponse(
        open(abs_path, 'rb'), content_type=content_type or 'application/octet-stream',
    )
    response['Content-Disposition'] = f'attachment; filename="{doc["file_name"]}"'
    return response
