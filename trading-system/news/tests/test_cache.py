import unittest
from news.cache.memory_cache import MemoryCache


class TestMemoryCache(unittest.TestCase):
    def setUp(self):
        self.cache = MemoryCache({"ttl": 60})

    def test_set_and_get(self):
        self.cache.set("key1", "value1")
        value = self.cache.get("key1")
        self.assertEqual(value, "value1")

    def test_get_nonexistent(self):
        value = self.cache.get("nonexistent")
        self.assertIsNone(value)

    def test_delete(self):
        self.cache.set("key1", "value1")
        result = self.cache.delete("key1")
        self.assertTrue(result)
        value = self.cache.get("key1")
        self.assertIsNone(value)

    def test_delete_nonexistent(self):
        result = self.cache.delete("nonexistent")
        self.assertFalse(result)

    def test_clear(self):
        self.cache.set("key1", "value1")
        self.cache.set("key2", "value2")
        self.cache.clear()
        self.assertEqual(self.cache.size(), 0)

    def test_exists(self):
        self.cache.set("key1", "value1")
        self.assertTrue(self.cache.exists("key1"))
        self.assertFalse(self.cache.exists("nonexistent"))

    def test_get_many(self):
        self.cache.set("key1", "value1")
        self.cache.set("key2", "value2")
        result = self.cache.get_many(["key1", "key2", "key3"])
        self.assertEqual(len(result), 2)
        self.assertIn("key1", result)
        self.assertIn("key2", result)

    def test_set_many(self):
        items = {"key1": "value1", "key2": "value2"}
        self.cache.set_many(items)
        self.assertEqual(self.cache.get("key1"), "value1")
        self.assertEqual(self.cache.get("key2"), "value2")

    def test_size(self):
        self.cache.set("key1", "value1")
        self.cache.set("key2", "value2")
        self.assertEqual(self.cache.size(), 2)


if __name__ == "__main__":
    unittest.main()
