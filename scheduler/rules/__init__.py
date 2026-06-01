"""Rule registry package.

Importing this package loads the hard and soft rule modules so their register
decorators run and populate the registries. The hard and soft modules arrive in
a later stage, so the auto import is wired then.
"""
