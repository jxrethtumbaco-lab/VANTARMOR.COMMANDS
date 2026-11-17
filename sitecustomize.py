"""Temporary compatibility shim for legacy annotations in project modules."""
import builtins
from typing import Optional

# Some project modules use Optional in annotations without importing it.
builtins.Optional = Optional
