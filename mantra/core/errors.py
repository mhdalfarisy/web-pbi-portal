"""Respons standar saat data Power BI gagal diambil.

User hanya melihat pesan umum + kode referensi. Detail error (path API berisi ID workspace/dataset, isi respons Power
BI) hanya ditulis ke log server, dicari lewat kode referensi yang sama.
"""
import secrets
import time

from flask import Response, current_app, jsonify, render_template

from .common import stamp_info

PUBLIC_MESSAGE = "Could not load data from Power BI. Please try again in a moment."


def log_data_error(exc):
    """Catat error lengkap ke log, kembalikan kode referensi pendek untuk ditampilkan ke user."""
    ref = secrets.token_hex(4).upper()
    current_app.logger.error("Power BI request failed [ref %s]: %s", ref, exc, exc_info=exc)
    return ref


def data_error_page(exc):
    return render_template("dashboard/error.html", ref=log_data_error(exc), header=stamp_info(time.time())), 502


def data_error_json(exc):
    ref = log_data_error(exc)
    return jsonify(error=f"{PUBLIC_MESSAGE} (ref {ref})", ref=ref), 502


def data_error_text(exc):
    return Response(f"{PUBLIC_MESSAGE} (ref {log_data_error(exc)})", status=502, mimetype="text/plain")
