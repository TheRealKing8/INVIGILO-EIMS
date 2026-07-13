"""INVIGILO Django apps.

Each subdirectory is a self-contained Django app. Cross-app imports of
models are permitted only when one app owns a foreign key to another,
and only via ``apps.<x>.models.<Model>`` references. Anything else
circles back through the project package.
"""