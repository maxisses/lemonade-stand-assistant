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
          m$cancelled_requests == 0, m$sources$presenter$total == 10,
          m$sources$audience$total == 0, m$sources$automation$total == 0,
          sum(unlist(m$detections_by_detector)) == 3,
          m$total_requests == m$approved_requests + m$blocked_requests + m$service_errors + m$rejected_requests + m$active_requests)
cat("Dashboard UI construction and request-outcome reconciliation passed.\n")

# Mixed source accounting keeps presenter traffic and detector hits out of the race.
source_fixture <- paste(
  fixture,
  'guardrail_requests_total{source="audience_product",mode="protected"} 3',
  'guardrail_request_outcomes_total{source="audience_product",mode="protected",outcome="allowed"} 1',
  'guardrail_request_outcomes_total{source="audience_product",mode="protected",outcome="blocked"} 1',
  'guardrail_request_outcomes_total{source="audience_product",mode="protected",outcome="cancelled"} 1',
  'guardrail_requests_total{source="audience_customer",mode="protected"} 4',
  'guardrail_request_outcomes_total{source="audience_customer",mode="protected",outcome="allowed"} 2',
  'guardrail_request_outcomes_total{source="audience_customer",mode="protected",outcome="error"} 1',
  'guardrail_active_requests{source="audience_customer",mode="protected"} 1',
  'guardrail_requests_total{source="audience_attacker",mode="protected"} 5',
  'guardrail_request_outcomes_total{source="audience_attacker",mode="protected",outcome="blocked"} 2',
  'guardrail_request_outcomes_total{source="audience_attacker",mode="protected",outcome="rejected"} 1',
  'guardrail_request_outcomes_total{source="audience_attacker",mode="protected",outcome="error"} 1',
  'guardrail_active_requests{source="audience_attacker",mode="protected"} 1',
  'guardrail_requests_total{source="automation",mode="protected"} 9',
  'guardrail_request_outcomes_total{source="automation",mode="protected",outcome="allowed"} 2',
  'guardrail_request_outcomes_total{source="automation",mode="protected",outcome="blocked"} 3',
  'guardrail_request_outcomes_total{source="automation",mode="protected",outcome="error"} 1',
  'guardrail_request_outcomes_total{source="automation",mode="protected",outcome="rejected"} 1',
  'guardrail_request_outcomes_total{source="automation",mode="protected",outcome="cancelled"} 1',
  'guardrail_active_requests{source="automation",mode="protected"} 1',
  'guardrail_detections_by_detector{source="automation",detector="hap"} 8',
  'guardrail_request_outcomes_total{source="automation",mode="protected",outcome="unknown_future_value"} 0',
  sep = "\n"
)
m <- scope$parse_prometheus_metrics(source_fixture)
audience <- m$sources$audience
automation <- m$sources$automation
stopifnot(m$total_requests == 31, audience$total == 12, automation$total == 9,
          audience$allowed == 3, audience$blocked == 3, audience$error == 2,
          audience$rejected == 1, audience$cancelled == 1, audience$pending == 2,
          automation$allowed == 2, automation$blocked == 3, automation$error == 1,
          automation$rejected == 1, automation$cancelled == 1, automation$pending == 1,
          m$cancelled_requests == 2,
          sum(unlist(m$detections_by_detector)) == 11,
          audience$total == sum(unlist(audience[names(audience) != "total"])),
          automation$total == sum(unlist(automation[names(automation) != "total"])),
          m$total_requests == m$approved_requests + m$blocked_requests + m$service_errors +
            m$rejected_requests + m$cancelled_requests + m$active_requests)
cat("Audience/automation source aggregation, cancellations, and unknown-outcome handling passed.\n")
