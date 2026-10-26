"""Cache hasil query di memori. Setiap dashboard membuat Cache sendiri, jadi kuncinya tidak bisa bentrok."""
import threading
import time


class Cache:
    """Simpan hasil query selama ttl detik. get() mengembalikan (data, waktu diambil).

    Request bersamaan untuk key yang sama saat cache kosong menunggu satu load() saja (tidak menjalankan query
    Power BI yang sama berkali-kali). Error dari load() tidak di-cache.
    """

    def __init__(self, ttl, size=300):
        self.ttl, self.size = ttl, size
        self.items = {}
        self.loading = {}  # key -> Lock milik load() yang sedang berjalan
        self.lock = threading.Lock()

    def _fresh(self, key):
        hit = self.items.get(key)
        return hit if hit and time.time() - hit[1] < self.ttl else None

    def get(self, key, load):
        with self.lock:
            hit = self._fresh(key)
            if hit:
                return hit
            key_lock = self.loading.setdefault(key, threading.Lock())
        with key_lock:
            with self.lock:
                hit = self._fresh(key)  # sudah dimuat thread lain selagi menunggu
                if hit:
                    return hit
            try:
                value = (load(), time.time())
            except BaseException:
                with self.lock:
                    self.loading.pop(key, None)
                raise
            with self.lock:
                self.items[key] = value
                self.loading.pop(key, None)  # dilepas setelah hasil tersimpan, supaya tidak ada load() kedua
                if len(self.items) > self.size:
                    for old in sorted(self.items, key=lambda k: self.items[k][1])[: len(self.items) - self.size]:
                        del self.items[old]
            return value
