"""Keep the fixture data out of collection.

The family's templates are inputs to the composition scenarios, not tests: their
extension modules would otherwise be imported and scanned for doctests.
"""

collect_ignore_glob = ["family/*"]
