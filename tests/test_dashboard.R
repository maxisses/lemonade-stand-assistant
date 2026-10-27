# Run with Rscript tests/test_dashboard.R path/to/shiny-app.R.
# This checks real dashboard parsing without making model requests or starting Shiny.
path <- commandArgs(trailingOnly = TRUE)[1]
expressions <- parse(path)
scope <- new.env(parent = globalenv())
# The final expression starts the app; all preceding expressions define the UI/server.
for (expression in expressions[-length(expressions)]) eval(expression, scope)
fixture <- paste(
  'guardrail_requests_total{source="presenter",mode="protected"} 10',
  'guardrail_request_outcomes_total{source="presenter",mode="protected",outcome="allowed"} 2',
  'guardrail_request_outcomes_total{source="presenter",mode="protected",outcome="blocked"} 1',
  'guardrail_request_outcomes_total{source="presenter",mode="protected",outcome="error"} 1',
  'guardrail_request_outcomes_total{source="presenter",mode="protected",outcome="rejected"} 1',
  'guardrail_active_requests{source="presenter",mode="protected"} 5',
  'guardrail_detections_by_detector{source="presenter",detector="hap"} 2',
  'guardrail_detections_by_detector{source="presenter",detector="language_detection"} 1',
  sep = "\n"
)
m <- scope$parse_prometheus_metrics(fixture)
stopifnot(m$total_requests == 10, m$approved_requests == 2, m$blocked_requests == 1,
          m$service_errors == 1, m$rejected_requests == 1, m$active_requests == 5,
          sum(unlist(m$detections_by_detector)) == 3,
          m$total_requests == m$approved_requests + m$blocked_requests + m$service_errors + m$rejected_requests + m$active_requests)
cat("Dashboard UI construction and request-outcome reconciliation passed.\n")
