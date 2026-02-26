from prometheus_client import Counter, Histogram

alerts_received_total = Counter(
    "alerts_received_total",
    "Total number of alerts received via webhooks",
    ["source"],
)

webhook_requests_total = Counter(
    "webhook_requests_total",
    "Total webhook requests (accepted)",
    ["source"],
)

webhook_db_write_latency_seconds = Histogram(
    "webhook_db_write_latency_seconds",
    "Latency of writing webhook alert to database",
    ["source"],
)

api_request_latency_seconds = Histogram(
    "api_request_latency_seconds",
    "API request latency in seconds",
    ["route", "method", "status"],
)

time_to_contain_seconds = Histogram(
    "time_to_contain_seconds",
    "Time from case creation to case close (seconds)",
    ["type", "severity"],
)
