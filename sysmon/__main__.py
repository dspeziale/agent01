"""
Sysmon backwards compatibility CLI wrapper for Pulsar.
"""
try:
    from pulsar.__main__ import main
except ImportError:
    from .__main__ import main  # pragma: no cover

if __name__ == "__main__":
    main()
