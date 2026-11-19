"""
ApexVault: Showcase Proof of Work built under ApexEngine v2.0.
A high-performance, thread-safe, transactional key-value & event streaming engine.
"""

from .apex_vault import (
    ApexVault,
    TransactionConflictError,
    KeyNotFoundError,
    TransactionNotFoundError,
)

__all__ = [
    "ApexVault",
    "TransactionConflictError",
    "KeyNotFoundError",
    "TransactionNotFoundError",
]
