"""Cache hasil query di memori. Setiap dashboard membuat Cache sendiri, jadi kuncinya tidak bisa bentrok."""
import threading
import time


class Cache:
    """Simpan hasil query selama ttl detik. get() mengembalikan (data, waktu diambil)."""

    def __init__(self, ttl, size=300):
        self.ttl, self.size = ttl, size
        self.items = {}
        self.lock = threading.Lock()

    def get(self, key, load):
        with self.lock:
            hit = self.items.get(key)
            if hit and time.time() - hit[1] < self.ttl:
                return hit
        value = (load(), time.time())
        with self.lock:
            self.items[key] = value
            if len(self.items) > self.size:
                for old in sorted(self.items, key=lambda k: self.items[k][1])[: len(self.items) - self.size]:
                    del self.items[old]
        return value
