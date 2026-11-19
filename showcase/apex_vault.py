#!/usr/bin/env python3
"""
ApexVault: High-Performance Concurrent In-Memory Key-Value & Event Store.
Showcase Proof of Work developed strictly adhering to ApexEngine 4-Gate Protocol.

Features:
- Thread-safe in-memory key-value operations with RLock.
- TTL (Time-To-Live) expiration and periodic/on-demand sweep.
- LRU (Least Recently Used) automatic cache eviction.
- ACID-compliant optimistic transactions with conflict detection.
- Pub/Sub event streaming with wildcard pattern matching.
- Append-only Write-Ahead Log (WAL) with SHA-256 integrity checks and crash recovery.
- Zero third-party dependencies (100% Python standard library).
"""

import os
import re
import time
import json
import hashlib
import threading
from collections import OrderedDict
from typing import Any, Callable, Dict, List, Optional, Set, Tuple


class ApexVaultError(Exception):
    """Base exception for ApexVault errors."""


class TransactionConflictError(ApexVaultError):
    """Raised when an optimistic transaction conflicts with concurrent modifications."""


class KeyNotFoundError(ApexVaultError):
    """Raised when a requested key is not present in the vault."""


class TransactionNotFoundError(ApexVaultError):
    """Raised when a transaction ID is invalid or has already completed."""


class Entry:
    """Internal entry representation holding value, version, and expiration."""

    def __init__(self, value: Any, version: int = 1, expires_at: Optional[float] = None) -> None:
        self.value: Any = value
        self.version: int = version
        self.expires_at: Optional[float] = expires_at

    def is_expired(self, current_time: float) -> bool:
        if self.expires_at is None:
            return False
        return current_time >= self.expires_at


class TransactionContext:
    """Tracks staged changes and baseline version snapshots for a transaction."""

    def __init__(self, tx_id: str, snapshot_versions: Dict[str, int]) -> None:
        self.tx_id: str = tx_id
        self.snapshot_versions: Dict[str, int] = snapshot_versions
        self.staged_puts: Dict[str, Any] = {}
        self.staged_deletes: Set[str] = set()
        self.started_at: float = time.time()


class ApexVault:
    """
    High-performance thread-safe storage & event engine.
    Demonstrates flagship software architecture created under ApexEngine.
    """

    def __init__(
        self,
        max_capacity: Optional[int] = None,
        wal_path: Optional[str] = None,
        auto_recover: bool = False
    ) -> None:
        self._lock: threading.RLock = threading.RLock()
        self._store: OrderedDict[str, Entry] = OrderedDict()
        self._max_capacity: Optional[int] = max_capacity
        self._wal_path: Optional[str] = wal_path
        self._wal_file = None

        # Concurrency & Transactions
        self._active_transactions: Dict[str, TransactionContext] = {}
        self._tx_counter: int = 0

        # Pub/Sub Subscriptions: (sub_id, regex_pattern, callback)
        self._subscriptions: Dict[str, Tuple[re.Pattern, Callable[[str, Any], None]]] = {}
        self._sub_counter: int = 0

        # Telemetry & Metrics
        self._hits: int = 0
        self._misses: int = 0
        self._evictions: int = 0
        self._commits: int = 0
        self._rollbacks: int = 0

        # Initialize WAL if specified
        if self._wal_path:
            wal_dir = os.path.dirname(os.path.abspath(self._wal_path))
            if wal_dir and not os.path.exists(wal_dir):
                os.makedirs(wal_dir, exist_ok=True)
            self._wal_file = open(self._wal_path, "a", encoding="utf-8")
            if auto_recover and os.path.exists(self._wal_path):
                self.recover_from_wal()

    def __del__(self) -> None:
        """Ensure WAL file descriptor is closed cleanly."""
        self.close()

    def close(self) -> None:
        """Explicitly closes open file descriptors (WAL journal)."""
        with self._lock:
            if self._wal_file and not self._wal_file.closed:
                try:
                    self._wal_file.flush()
                    self._wal_file.close()
                except Exception:
                    self._wal_file = None
                self._wal_file = None

    def __enter__(self) -> "ApexVault":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()

    # -------------------------------------------------------------------------
    # Core Key-Value Store Operations
    # -------------------------------------------------------------------------

    def put(self, key: str, value: Any, ttl: Optional[float] = None) -> None:
        """Stores a key-value pair with optional TTL in seconds."""
        if not isinstance(key, str) or not key:
            raise ValueError("Key must be a non-empty string")

        with self._lock:
            now = time.time()
            expires_at = (now + ttl) if ttl is not None else None

            # Check if key exists to update version
            current_entry = self._store.get(key)
            new_version = (current_entry.version + 1) if current_entry else 1

            # Check capacity eviction before insertion
            if self._max_capacity and key not in self._store and len(self._store) >= self._max_capacity:
                self._evict_lru()

            self._store[key] = Entry(value=value, version=new_version, expires_at=expires_at)
            self._store.move_to_end(key)

            # Record to WAL
            self._append_wal("PUT", key=key, val=value, expires_at=expires_at)

    def get(self, key: str, default: Any = None) -> Any:
        """Retrieves value for key, returning default if absent or expired."""
        with self._lock:
            now = time.time()
            entry = self._store.get(key)
            if entry is None:
                self._misses += 1
                return default

            if entry.is_expired(now):
                del self._store[key]
                self._misses += 1
                self._evictions += 1
                return default

            # Refresh LRU access position
            self._store.move_to_end(key)
            self._hits += 1
            return entry.value

    def has(self, key: str) -> bool:
        """Checks if key exists and is unexpired."""
        with self._lock:
            now = time.time()
            entry = self._store.get(key)
            if entry is None:
                return False
            if entry.is_expired(now):
                del self._store[key]
                self._evictions += 1
                return False
            return True

    def delete(self, key: str) -> bool:
        """Deletes key from store. Returns True if deleted, False if absent."""
        with self._lock:
            if key in self._store:
                del self._store[key]
                self._append_wal("DEL", key=key)
                return True
            return False

    def keys(self) -> List[str]:
        """Returns list of unexpired keys currently in the vault."""
        with self._lock:
            self._purge_expired()
            return list(self._store.keys())

    def size(self) -> int:
        """Returns count of active unexpired items."""
        with self._lock:
            self._purge_expired()
            return len(self._store)

    # -------------------------------------------------------------------------
    # Eviction & Cleanup Policies
    # -------------------------------------------------------------------------

    def _evict_lru(self) -> None:
        """Evicts the least-recently used unexpired key."""
        # Clean expired items first
        if self._purge_expired() > 0:
            if self._max_capacity and len(self._store) < self._max_capacity:
                return

        if self._store:
            oldest_key, _ = self._store.popitem(last=False)
            self._evictions += 1
            self._append_wal("EVICT", key=oldest_key)

    def _purge_expired(self) -> int:
        """Purges all expired entries. Returns number of purged items."""
        now = time.time()
        expired_keys = [k for k, entry in self._store.items() if entry.is_expired(now)]
        for k in expired_keys:
            del self._store[k]
            self._evictions += 1
        return len(expired_keys)

    # -------------------------------------------------------------------------
    # ACID-Compliant Optimistic Transactions
    # -------------------------------------------------------------------------

    def begin_transaction(self) -> str:
        """Starts a new transaction and returns its unique ID."""
        with self._lock:
            self._tx_counter += 1
            tx_id = f"tx_{self._tx_counter}_{int(time.time() * 1000)}"

            # Snapshot current versions of all keys
            now = time.time()
            snapshots = {
                k: entry.version
                for k, entry in self._store.items()
                if not entry.is_expired(now)
            }
            self._active_transactions[tx_id] = TransactionContext(tx_id, snapshots)
            return tx_id

    def tx_put(self, tx_id: str, key: str, value: Any) -> None:
        """Stages a put operation within an active transaction."""
        with self._lock:
            tx = self._active_transactions.get(tx_id)
            if not tx:
                raise TransactionNotFoundError(f"Unknown or closed transaction: {tx_id}")
            tx.staged_puts[key] = value
            tx.staged_deletes.discard(key)

    def tx_delete(self, tx_id: str, key: str) -> None:
        """Stages a delete operation within an active transaction."""
        with self._lock:
            tx = self._active_transactions.get(tx_id)
            if not tx:
                raise TransactionNotFoundError(f"Unknown or closed transaction: {tx_id}")
            tx.staged_deletes.add(key)
            tx.staged_puts.pop(key, None)

    def commit_transaction(self, tx_id: str) -> None:
        """
        Commits all staged transaction changes atomically.
        Detects conflicts if any modified key was altered concurrently.
        """
        with self._lock:
            tx = self._active_transactions.get(tx_id)
            if not tx:
                raise TransactionNotFoundError(f"Unknown or closed transaction: {tx_id}")

            # Verify optimistic snapshot versions
            for k in set(tx.staged_puts.keys()).union(tx.staged_deletes):
                current_entry = self._store.get(k)
                current_version = current_entry.version if current_entry else 0
                snapshot_version = tx.snapshot_versions.get(k, 0)

                if current_version != snapshot_version:
                    self._rollbacks += 1
                    del self._active_transactions[tx_id]
                    raise TransactionConflictError(
                        f"Conflict detected on key '{k}': expected v{snapshot_version}, found v{current_version}"
                    )

            # Apply all deletes
            for k in tx.staged_deletes:
                if k in self._store:
                    del self._store[k]
                    self._append_wal("DEL", key=k)

            # Apply all puts
            for k, val in tx.staged_puts.items():
                current_entry = self._store.get(k)
                new_version = (current_entry.version + 1) if current_entry else 1
                self._store[k] = Entry(value=val, version=new_version)
                self._store.move_to_end(k)
                self._append_wal("PUT", key=k, val=val)

            self._commits += 1
            del self._active_transactions[tx_id]

    def rollback_transaction(self, tx_id: str) -> None:
        """Rolls back and discards staged transaction operations."""
        with self._lock:
            if tx_id in self._active_transactions:
                del self._active_transactions[tx_id]
                self._rollbacks += 1
            else:
                raise TransactionNotFoundError(f"Unknown or closed transaction: {tx_id}")

    # -------------------------------------------------------------------------
    # Pub/Sub Event Streaming
    # -------------------------------------------------------------------------

    def subscribe(self, pattern: str, callback: Callable[[str, Any], None]) -> str:
        """
        Subscribes to events matching a wildcard pattern (e.g., 'orders.*', '*').
        Returns unique subscription ID.
        """
        if not callable(callback):
            raise TypeError("Subscription callback must be callable")

        with self._lock:
            self._sub_counter += 1
            sub_id = f"sub_{self._sub_counter}"

            # Convert glob-like pattern to regex
            regex_str = "^" + re.escape(pattern).replace(r"\*", r".*") + "$"
            compiled_pat = re.compile(regex_str)
            self._subscriptions[sub_id] = (compiled_pat, callback)
            return sub_id

    def unsubscribe(self, sub_id: str) -> bool:
        """Removes an active subscription."""
        with self._lock:
            if sub_id in self._subscriptions:
                del self._subscriptions[sub_id]
                return True
            return False

    def publish(self, topic: str, message: Any) -> int:
        """
        Publishes message to topic. Dispatches to all matching subscribers.
        Returns the number of subscribers notified.
        """
        dispatched_count = 0
        callbacks_to_invoke: List[Tuple[Callable[[str, Any], None], str, Any]] = []

        with self._lock:
            for _, (pattern, callback) in self._subscriptions.items():
                if pattern.match(topic):
                    callbacks_to_invoke.append((callback, topic, message))

        # Invoke callbacks outside lock to avoid deadlocks
        for cb, top, msg in callbacks_to_invoke:
            try:
                cb(top, msg)
                dispatched_count += 1
            except Exception as e:
                # Callback isolation: errors in listeners do not crash the publisher
                print(f"[ApexVault Warning] Listener error on topic '{top}': {e}")

        return dispatched_count

    # -------------------------------------------------------------------------
    # Write-Ahead Log (WAL) Durability & Recovery
    # -------------------------------------------------------------------------

    def _append_wal(self, op: str, **kwargs: Any) -> None:
        """Appends operation to WAL with SHA-256 integrity checksum."""
        if not self._wal_file or self._wal_file.closed:
            return

        record = {
            "op": op,
            "data": kwargs,
            "ts": time.time(),
        }
        raw_payload = json.dumps(record, sort_keys=True)
        checksum = hashlib.sha256(raw_payload.encode("utf-8")).hexdigest()
        line = json.dumps({"payload": record, "checksum": checksum}) + "\n"
        self._wal_file.write(line)
        self._wal_file.flush()

    def recover_from_wal(self) -> int:
        """
        Replays operations from WAL to reconstruct in-memory state.
        Verifies SHA-256 checksum for every record. Returns count of recovered ops.
        """
        if not self._wal_path or not os.path.exists(self._wal_path):
            return 0

        replayed_ops = 0
        with self._lock:
            # Temporarily flush file if open
            if self._wal_file and not self._wal_file.closed:
                self._wal_file.flush()

            with open(self._wal_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        entry = json.loads(line)
                        payload = entry["payload"]
                        expected_hash = entry["checksum"]

                        # Verify checksum integrity
                        raw_payload = json.dumps(payload, sort_keys=True)
                        computed_hash = hashlib.sha256(raw_payload.encode("utf-8")).hexdigest()

                        if computed_hash != expected_hash:
                            print(f"[ApexVault Recovery Error] Corrupted record detected. Skipping.")
                            continue

                        op = payload["op"]
                        data = payload["data"]

                        if op == "PUT":
                            key = data["key"]
                            val = data["val"]
                            exp = data.get("expires_at")
                            cur = self._store.get(key)
                            ver = (cur.version + 1) if cur else 1
                            self._store[key] = Entry(val, version=ver, expires_at=exp)
                            self._store.move_to_end(key)
                            replayed_ops += 1
                        elif op == "DEL" or op == "EVICT":
                            key = data["key"]
                            if key in self._store:
                                del self._store[key]
                                replayed_ops += 1
                    except Exception as parse_err:
                        print(f"[ApexVault Recovery Error] Failed to parse WAL entry: {parse_err}")

        return replayed_ops

    # -------------------------------------------------------------------------
    # Telemetry & Diagnostics
    # -------------------------------------------------------------------------

    def get_stats(self) -> Dict[str, Any]:
        """Returns live performance telemetry and diagnostic metrics."""
        with self._lock:
            total_requests = self._hits + self._misses
            hit_ratio = (self._hits / total_requests) if total_requests > 0 else 0.0

            return {
                "active_keys": len(self._store),
                "total_requests": total_requests,
                "hits": self._hits,
                "misses": self._misses,
                "hit_ratio_percent": round(hit_ratio * 100, 2),
                "evictions": self._evictions,
                "active_transactions": len(self._active_transactions),
                "committed_transactions": self._commits,
                "aborted_transactions": self._rollbacks,
                "active_subscriptions": len(self._subscriptions),
                "wal_enabled": bool(self._wal_path),
            }
