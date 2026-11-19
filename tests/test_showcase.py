#!/usr/bin/env python3
"""
Unit and Integration Tests for ApexVault (Showcase Proof of Work).
Verifies ACID transactions, TTL, LRU eviction, Pub/Sub wildcard streams,
WAL crash recovery, and thread safety under concurrent load.
"""

import os
import time
import tempfile
import threading
import unittest
from pathlib import Path

# ApexVault import - will be implemented in showcase/apex_vault.py
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from showcase.apex_vault import (
    ApexVault,
    TransactionConflictError,
    KeyNotFoundError,
    TransactionNotFoundError,
)


class TestApexVaultBasic(unittest.TestCase):
    def setUp(self):
        self.vault = ApexVault()

    def test_basic_crud(self):
        self.assertFalse(self.vault.has("key1"))
        self.assertIsNone(self.vault.get("key1"))

        self.vault.put("key1", "val1")
        self.assertTrue(self.vault.has("key1"))
        self.assertEqual(self.vault.get("key1"), "val1")

        self.vault.put("key1", "val1_updated")
        self.assertEqual(self.vault.get("key1"), "val1_updated")

        self.vault.delete("key1")
        self.assertFalse(self.vault.has("key1"))
        self.assertIsNone(self.vault.get("key1"))

    def test_default_value(self):
        self.assertEqual(self.vault.get("nonexistent", "fallback"), "fallback")

    def test_ttl_expiration(self):
        # Set short TTL
        self.vault.put("ephemeral", "temp_data", ttl=0.1)
        self.assertTrue(self.vault.has("ephemeral"))
        self.assertEqual(self.vault.get("ephemeral"), "temp_data")

        # Sleep past TTL
        time.sleep(0.15)
        self.assertFalse(self.vault.has("ephemeral"))
        self.assertIsNone(self.vault.get("ephemeral"))

    def test_lru_eviction(self):
        # Max capacity 3
        lru_vault = ApexVault(max_capacity=3)
        lru_vault.put("a", 1)
        lru_vault.put("b", 2)
        lru_vault.put("c", 3)

        # Access 'a' so 'b' becomes the oldest unaccessed
        _ = lru_vault.get("a")

        # Insert 4th item -> should evict 'b'
        lru_vault.put("d", 4)
        self.assertTrue(lru_vault.has("a"))
        self.assertFalse(lru_vault.has("b"))
        self.assertTrue(lru_vault.has("c"))
        self.assertTrue(lru_vault.has("d"))


class TestApexVaultTransactions(unittest.TestCase):
    def setUp(self):
        self.vault = ApexVault()

    def test_atomic_commit(self):
        self.vault.put("balance_alice", 100)
        self.vault.put("balance_bob", 50)

        tx = self.vault.begin_transaction()
        self.vault.tx_put(tx, "balance_alice", 80)
        self.vault.tx_put(tx, "balance_bob", 70)

        # Main store still sees old values
        self.assertEqual(self.vault.get("balance_alice"), 100)
        self.assertEqual(self.vault.get("balance_bob"), 50)

        # Commit
        self.vault.commit_transaction(tx)

        # Main store sees new values
        self.assertEqual(self.vault.get("balance_alice"), 80)
        self.assertEqual(self.vault.get("balance_bob"), 70)

    def test_rollback(self):
        self.vault.put("key1", "original")

        tx = self.vault.begin_transaction()
        self.vault.tx_put(tx, "key1", "modified")
        self.vault.tx_put(tx, "key2", "new_val")

        self.vault.rollback_transaction(tx)

        self.assertEqual(self.vault.get("key1"), "original")
        self.assertFalse(self.vault.has("key2"))

    def test_optimistic_conflict_detection(self):
        self.vault.put("counter", 10)

        tx1 = self.vault.begin_transaction()
        tx2 = self.vault.begin_transaction()

        self.vault.tx_put(tx1, "counter", 11)
        self.vault.tx_put(tx2, "counter", 12)

        # Tx1 commits successfully
        self.vault.commit_transaction(tx1)
        self.assertEqual(self.vault.get("counter"), 11)

        # Tx2 tries to commit -> must raise conflict
        with self.assertRaises(TransactionConflictError):
            self.vault.commit_transaction(tx2)


class TestApexVaultPubSub(unittest.TestCase):
    def setUp(self):
        self.vault = ApexVault()

    def test_wildcard_pubsub(self):
        received_all = []
        received_orders = []

        sub1 = self.vault.subscribe("*", lambda t, m: received_all.append((t, m)))
        sub2 = self.vault.subscribe("order.*", lambda t, m: received_orders.append((t, m)))

        self.vault.publish("order.created", {"id": 101})
        self.vault.publish("order.cancelled", {"id": 102})
        self.vault.publish("user.login", {"id": 1})

        self.assertEqual(len(received_all), 3)
        self.assertEqual(len(received_orders), 2)
        self.assertEqual(received_orders[0][0], "order.created")
        self.assertEqual(received_orders[1][0], "order.cancelled")

        # Unsubscribe sub2
        self.vault.unsubscribe(sub2)
        self.vault.publish("order.shipped", {"id": 103})
        self.assertEqual(len(received_orders), 2)
        self.assertEqual(len(received_all), 4)


class TestApexVaultWAL(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.wal_file = os.path.join(self.temp_dir, "vault.wal")

    def tearDown(self):
        if os.path.exists(self.wal_file):
            os.remove(self.wal_file)
        os.rmdir(self.temp_dir)

    def test_wal_durability_and_crash_recovery(self):
        # 1. Instantiate vault with WAL and write data
        vault1 = ApexVault(wal_path=self.wal_file)
        vault1.put("k1", "v1")
        vault1.put("k2", "v2")
        vault1.put("k3", "v3")
        vault1.delete("k2")
        vault1.close()

        # 2. Simulate crash by instantiating new vault from disk WAL
        vault2 = ApexVault(wal_path=self.wal_file)
        recovered_count = vault2.recover_from_wal()

        self.assertEqual(recovered_count, 4)
        self.assertEqual(vault2.get("k1"), "v1")
        self.assertFalse(vault2.has("k2"))
        self.assertEqual(vault2.get("k3"), "v3")
        vault2.close()


class TestApexVaultConcurrency(unittest.TestCase):
    def setUp(self):
        self.vault = ApexVault()

    def test_concurrent_writes(self):
        def worker(w_id: int):
            for i in range(50):
                self.vault.put(f"worker_{w_id}_{i}", i)
                val = self.vault.get(f"worker_{w_id}_{i}")
                self.assertEqual(val, i)

        threads = [threading.Thread(target=worker, args=(t,)) for t in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(self.vault.size(), 250)


if __name__ == "__main__":
    unittest.main()
