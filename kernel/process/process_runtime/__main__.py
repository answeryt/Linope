"""Run one capability program. The caller owns when this program should leave."""

from kernel.process.process_runtime.runtime import serve_stdio

if __name__ == "__main__":
    serve_stdio()
