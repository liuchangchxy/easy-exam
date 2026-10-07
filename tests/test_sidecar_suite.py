"""
tests/test_sidecar_suite.py - Bridge to discover and run automation.sidecar.test_dispatcher
in EasyExam CI and local unittest discovery.
"""
import unittest
from automation.sidecar import test_dispatcher


def load_tests(loader, tests, pattern):
    """Expose test suite from automation.sidecar.test_dispatcher to unittest discovery."""
    return loader.loadTestsFromModule(test_dispatcher)


if __name__ == "__main__":
    unittest.main()
