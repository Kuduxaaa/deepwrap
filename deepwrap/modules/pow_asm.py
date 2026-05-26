from __future__ import annotations

import os
import struct
import urllib.request

from dataclasses import dataclass
from typing import Optional

from wasmtime import Instance, Store
from deepwrap.config import Config

@dataclass(frozen=True)
class PowChallenge:
    """
    Represents a DeepSeek proof-of-work challenge.

    This object contains all server-provided fields required to solve the
    challenge and build the `x-ds-pow-response` header.

    Attributes:
        algorithm:
            The PoW algorithm identifier returned by the API, such as
            "DeepSeekHashV1".

        challenge:
            The hex-encoded challenge string passed to the WASM solver.

        salt:
            The server-provided salt used to build the solver prefix.

        signature:
            The server-provided signature that must be echoed back unchanged
            in the PoW response payload.

        difficulty:
            The difficulty value passed to the WASM solver.

        expire_at:
            Challenge expiration timestamp in Unix milliseconds.

        expire_after:
            Challenge lifetime in milliseconds.

        target_path:
            The API path this challenge was issued for, such as
            "/api/v0/chat/completion".
    """

    algorithm: str
    challenge: str
    salt: str
    signature: str
    difficulty: int
    expire_at: int
    expire_after: int
    target_path: str


class ProofOfWorkSolver:
    """
    Solves DeepSeek proof-of-work challenges using the browser-compatible WASM module.

    Browser worker behavior:
        prefix = f"{salt}_{expireAt}_"
        wasm_solve(ret_ptr, challenge_ptr, challenge_len, prefix_ptr, prefix_len, difficulty)
        ok     = getInt32(ret_ptr + 0, little_endian=True)
        answer = getFloat64(ret_ptr + 8, little_endian=True)

    Notes:
        - The second string passed into the solver is the prefix, not the raw salt.
        - The final numeric argument is `difficulty` as float64.
        - `expire_at` is used only when building the prefix string.
    """

    def __init__(self, wasm_path: Optional[str] = None) -> None:
        """
        Initialize the solver.

        Args:
            wasm_path:
                Optional local path to the PoW WASM binary. If omitted, the WASM
                module is downloaded from the configured URL.
        """

        self._wasm_path = wasm_path
        self._wasm_bytes: Optional[bytes] = None
        self._engine = None
        self._module = None

    def _load_bytes(self) -> bytes:
        """
        Load the WASM module bytes.

        The bytes are loaded once and cached in memory. If `wasm_path` points
        to an existing file, that file is used. Otherwise, the module is
        downloaded from `Config.wasm_url`.

        Returns:
            The raw WASM bytes.
        """

        if self._wasm_bytes is not None:
            return self._wasm_bytes

        if self._wasm_path and os.path.isfile(self._wasm_path):
            with open(self._wasm_path, "rb") as fh:
                self._wasm_bytes = fh.read()
            return self._wasm_bytes

        with urllib.request.urlopen(Config.wasm_url, timeout=20) as resp:
            self._wasm_bytes = resp.read()

        return self._wasm_bytes

    def _write(self, ptr: int, data: bytes, memory, store) -> None:
        """
        Write bytes into WASM linear memory.

        Args:
            ptr:
                Destination pointer inside WASM memory.
            data:
                Bytes to write.
            memory:
                Exported WASM memory object.
            store:
                The active WASM store.
        """
        
        raw = memory.data_ptr(store)

        for i, b in enumerate(data):
            raw[ptr + i] = b

    def _read(self, ptr: int, size: int, memory, store) -> bytes:
        """
        Read bytes from WASM linear memory.

        Args:
            ptr:
                Source pointer inside WASM memory.
            size:
                Number of bytes to read.
            memory:
                Exported WASM memory object.
            store:
                The active WASM store.

        Returns:
            The bytes read from WASM memory.
        """

        return bytes(memory.data_ptr(store)[ptr + i] for i in range(size))

    def _pass_string(self, value: str, malloc, realloc, memory, store) -> tuple[int, int]:
        """
        Copy a Python string into WASM memory.

        This mirrors the wasm-bindgen string-passing behavior used by the
        browser worker. ASCII-only strings use a fast path; non-ASCII strings
        fall back to reallocation-based UTF-8 encoding.

        Args:
            value:
                The Python string to copy.
            malloc:
                WASM malloc export.
            realloc:
                WASM realloc export.
            memory:
                Exported WASM memory object.
            store:
                The active WASM store.

        Returns:
            A tuple of `(ptr, length)` describing the copied UTF-8 string in
            WASM memory.
        """

        encoded = value.encode("utf-8")

        if all(b < 128 for b in encoded):
            ptr = malloc(store, len(encoded), 1)
            self._write(ptr, encoded, memory, store)

            return ptr, len(encoded)

        ptr = malloc(store, len(value), 1)
        raw = memory.data_ptr(store)
        offset = 0

        while offset < len(value):
            ch = ord(value[offset])

            if ch > 127:
                break

            raw[ptr + offset] = ch
            offset += 1

        if offset != len(value):
            remainder = value[offset:].encode("utf-8")
            ptr = realloc(store, ptr, len(value), offset + len(remainder), 1)
            self._write(ptr + offset, remainder, memory, store)

            return ptr, offset + len(remainder)

        return ptr, offset

    def warmup(self) -> None:
        """
        Preload and compile the WASM module.

        This reduces latency for the first challenge solve by downloading and
        compiling the module ahead of time. Repeated calls are no-ops.

        Raises:
            RuntimeError:
                If the `wasmtime` dependency is missing.
        """

        if self._module is not None:
            return

        try:
            from wasmtime import Engine, Module

        except ImportError as exc:
            raise RuntimeError(
                "Missing dependency: wasmtime. Install it with: pip install wasmtime"
            ) from exc

        self._engine = Engine()
        self._module = Module(self._engine, self._load_bytes())

    def solve(self, challenge: PowChallenge) -> int:
        """
        Solve a DeepSeek proof-of-work challenge.

        Args:
            challenge:
                The server-issued proof-of-work challenge.

        Returns:
            The integer nonce that satisfies the challenge.

        Raises:
            RuntimeError:
                If the WASM solver reports that no valid solution was found.
        """

        if self._module is None:
            self.warmup()

        store = Store(self._engine)
        instance = Instance(store, self._module, [])
        exports = instance.exports(store)

        memory = exports["memory"]
        malloc = exports["__wbindgen_export_0"]
        realloc = exports["__wbindgen_export_1"]
        stack_ptr_fn = exports["__wbindgen_add_to_stack_pointer"]
        wasm_solve = exports["wasm_solve"]

        challenge_ptr, challenge_len = self._pass_string(
            challenge.challenge, malloc, realloc, memory, store
        )
        
        prefix_ptr, prefix_len = self._pass_string(
            f"{challenge.salt}_{challenge.expire_at}_", 
            malloc, 
            realloc, 
            memory, 
            store
        )

        ret_ptr = stack_ptr_fn(store, -16)
        try:
            wasm_solve(
                store,
                ret_ptr,
                challenge_ptr,
                challenge_len,
                prefix_ptr,
                prefix_len,
                float(challenge.difficulty),
            )

            raw = self._read(ret_ptr, 16, memory, store)
            ok = struct.unpack_from("<i", raw, 0)[0]
            answer = struct.unpack_from("<d", raw, 8)[0]

        finally:
            stack_ptr_fn(store, 16)

        if ok == 0:
            raise RuntimeError(
                "No solution found: "
                f"algorithm={challenge.algorithm}, "
                f"challenge={challenge.challenge}, "
                f"difficulty={challenge.difficulty}, "
            )

        return int(answer)