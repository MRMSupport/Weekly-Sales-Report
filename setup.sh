#!/bin/bash
# Routine environment setup script — intentionally a NO-OP.
# build_report.py now emits HTML using only the Python standard library, so
# there are no dependencies to install (reportlab / ghostscript / qpdf are gone;
# the queue mailer renders the PDF on Google's side). Kept for compatibility so
# any routine config pointing at setup.sh still succeeds.
echo "No dependencies to install (build_report.py is stdlib-only HTML)."
