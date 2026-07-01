#!/bin/bash
# Routine environment setup script (runs once, then cached).
# Installs the only dependency build_report.py needs beyond the base image.
pip install --break-system-packages reportlab || pip install reportlab
