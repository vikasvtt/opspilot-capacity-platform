from prometheus_client import Counter, Histogram

HTTP_REQUESTS = Counter("opspilot_http_requests_total", "HTTP requests", ["method", "status"])
HTTP_ERRORS = Counter("opspilot_http_errors_total", "HTTP responses with errors", ["method", "status"])
HTTP_LATENCY = Histogram("opspilot_http_request_duration_seconds", "Request duration", ["method"])
AGENT_CALLS = Counter("opspilot_agent_calls_total", "Placement proposal attempts", ["result"])
APPROVAL_DECISIONS = Counter("opspilot_approval_decisions_total", "Human approval decisions", ["decision"])
