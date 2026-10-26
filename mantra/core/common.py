"""Helper yang dipakai semua dashboard: zona waktu WIB, cap waktu di header, escape string DAX, URL logo."""
from datetime import datetime, timedelta, timezone

WIB = timezone(timedelta(hours=7))


def now_wib():
    return datetime.now(WIB)


def stamp_info(ts):
    """Timestamp (detik) -> {"date": "dd/mm/yyyy", "time": "HH:MM WIB"} untuk kotak Last Update di header."""
    dt = datetime.fromtimestamp(ts, WIB)
    return {"date": dt.strftime("%d/%m/%Y"), "time": dt.strftime("%H:%M WIB")}


def dax_str(value):
    """Literal string DAX yang aman: tanda kutip di-escape dengan menggandakannya."""
    return '"' + str(value).replace('"', '""') + '"'


def fix_logo_url(url):
    # i.ibb.co diblokir di beberapa jaringan; domain i.ibb.co.com melayani file yang sama
    return (url or "").replace("//i.ibb.co/", "//i.ibb.co.com/")
