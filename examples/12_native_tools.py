from tempfile import TemporaryDirectory

from deepwrap import NativeTools


# NativeTools can also be used directly without asking the model to select them.
# This example operates only inside a temporary directory.
with TemporaryDirectory() as directory:
    tools = NativeTools(working_directory=directory, timeout=10)

    print("=== WRITE ===")
    print(tools.write_file("notes/example.txt", "DeepWrap agent mode\nversion = 1\n"))

    print("\n=== READ ===")
    print(tools.read_file("notes/example.txt")["content"])

    print("=== EDIT ===")
    print(tools.edit_file("notes/example.txt", "version = 1", "version = 2"))

    print("\n=== GREP ===")
    print(tools.grep(r"version\s*=\s*\d+", glob=["*.txt", "**/*.txt"]))

    print("\n=== SYSTEM COMMAND ===")
    print(tools.exec("pwd"))

    print("\n=== PYTHON CODE ===")
    print(tools.exec_code("from pathlib import Path; print(list(Path('.').rglob('*')))"))
