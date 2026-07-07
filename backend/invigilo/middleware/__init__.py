"""Project-level middleware.

RequestIDMiddleware
    Assigns a UUIDv4 to every request and echoes it back via the
    ``X-Request-ID`` response header. The id is also attached to the
    logging context.

AuditContextMiddleware
    Binds the current ``request.user`` to a thread-local so the
    ``audit.services.record`` helper can pick up the actor without it
    having to be passed explicitly from every call site.
"""
