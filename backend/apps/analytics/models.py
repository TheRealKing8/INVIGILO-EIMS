"""Analytics has no tables — it's a read-only aggregator over the
other apps' models. The endpoint at ``/api/v1/analytics/summary/``
joins exam / allocation / attendance / incident data into a single
flat response for the control-room dashboard.

Keeping the app as a model-less service module lets us add it to
``INSTALLED_APPS`` for the OpenAPI tag + URL include without
registering a ``migrate`` step.
"""
