from datetime import date

from PyQt6.QtPrintSupport import QPrinter, QPrintDialog
from PyQt6.QtGui import QTextDocument

COMPANY_NAME = "Your Company"


def print_document(html: str, title: str, parent=None) -> None:
    """Open the system print dialog and render html to the selected printer."""
    printer = QPrinter(QPrinter.PrinterMode.HighResolution)
    printer.setDocName(title)
    dlg = QPrintDialog(printer, parent)
    if dlg.exec() != QPrintDialog.DialogCode.Accepted:
        return
    doc = QTextDocument()
    doc.setHtml(html)
    doc.print_(printer)


def doc_header(subtitle: str) -> str:
    today = date.today().strftime("%B %d, %Y")
    return (
        f'<div style="text-align:center;border-bottom:2px solid black;'
        f'padding-bottom:8px;margin-bottom:16px;font-family:Arial,sans-serif;">'
        f'<h2 style="margin:0;font-size:16pt;">{COMPANY_NAME}</h2>'
        f'<p style="margin:4px 0;font-size:11pt;font-weight:bold;">{subtitle}</p>'
        f'<p style="margin:0;font-size:9pt;color:#555;">Printed {today}</p>'
        f'</div>'
    )


_TH = ('background:rgb(0,60,180);color:white;padding:6px 8px;'
       'text-align:left;border:1px solid #999;font-size:10pt;')
_TD = 'padding:5px 8px;border:1px solid #ccc;font-size:10pt;vertical-align:top;'
_TABLE = 'border-collapse:collapse;width:100%;margin-bottom:14px;'


def th(text: str) -> str:
    return f'<th style="{_TH}">{text}</th>'


def td(text: str) -> str:
    return f'<td style="{_TD}">{text or ""}</td>'


def wrap_html(body: str) -> str:
    return (
        '<html><body style="font-family:Arial,sans-serif;'
        'font-size:10pt;margin:20px;">'
        + body
        + '</body></html>'
    )


def fields_table(rows: list[tuple[str, str]]) -> str:
    cells = "".join(
        f'<tr><td style="{_TD}font-weight:bold;color:#003cb4;white-space:nowrap;">'
        f'{label}</td><td style="{_TD}">{value or ""}</td></tr>'
        for label, value in rows
    )
    return f'<table style="{_TABLE}">{cells}</table>'


def data_table(headers: list[str], rows: list[list[str]]) -> str:
    head = "<tr>" + "".join(th(h) for h in headers) + "</tr>"
    body = "".join(
        "<tr>" + "".join(td(c) for c in row) + "</tr>"
        for row in rows
    )
    return f'<table style="{_TABLE}"><thead>{head}</thead><tbody>{body}</tbody></table>'
