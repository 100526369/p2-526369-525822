#!/usr/bin/env python3

import os
import subprocess
import sys
from pathlib import Path


def main():
    if len(sys.argv) != 3:
        print(
            f"Usage: {Path(sys.argv[0]).name} <input-file> <output-file>",
            file=sys.stderr,
        )
        return 1

    input_file = sys.argv[1]
    output_file = sys.argv[2]

    script_dir = Path(__file__).resolve().parent
    executable = script_dir / "sol-1"

    if not executable.is_file() or not os.access(executable, os.X_OK):
        print(
            f"Error: executable not found or not executable: {executable}\n"
            "Run 'make' to compile the program.",
            file=sys.stderr,
        )
        return 1

    try:
        result = subprocess.run(
            [str(executable), input_file, output_file],
            check=False,
            text=True,
        )

        if result.returncode < 0:
            print(
                f"Error: program terminated by signal {-result.returncode}.",
                file=sys.stderr,
            )
            return 128 - result.returncode

        return result.returncode

    except OSError as error:
        print(f"Error executing program: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
