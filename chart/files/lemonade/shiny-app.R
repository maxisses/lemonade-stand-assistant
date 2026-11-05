library(shiny)
library(httr)
library(stringr)
library(bslib)

# Configuration
METRICS_URL <- Sys.getenv("METRICS_URL", "http://lemonade-stand:8080/metrics")
REFRESH_INTERVAL <- as.integer(Sys.getenv("REFRESH_INTERVAL", "1")) # seconds
CONTROL_URL <- Sys.getenv("CONTROL_URL", "")

# Sources are assigned by the application, not by browser request headers.
empty_source <- function() list(total = 0, allowed = 0, blocked = 0, error = 0,
                                rejected = 0, cancelled = 0, pending = 0)
source_group <- function(source) {
  if (!is.na(source) && startsWith(source, "audience_")) return("audience")
  if (!is.na(source) && source %in% c("automation", "presenter")) return(source)
  return("other")
}

# Parse Prometheus metrics format
parse_prometheus_metrics <- function(metrics_text) {
  lines <- strsplit(metrics_text, "\n")[[1]]

  metrics <- list(
    total_requests = 0,
    blocked_requests = 0,
    service_errors = 0,
    approved_requests = 0,
    rejected_requests = 0,
    active_requests = 0,
    cancelled_requests = 0,
    sources = list(audience = empty_source(), automation = empty_source(),
                   presenter = empty_source(), other = empty_source()),
    source_detections = list(audience = list(), automation = list(), presenter = list(), other = list()),
    detections_by_detector = list()
  )

  for (line in lines) {
    # Skip comments and empty lines
    if (grepl("^#", line) || nchar(trimws(line)) == 0) next

    source <- str_match(line, 'source="([^"]+)"')[2]
    group <- source_group(source)

    # Parse guardrail_requests_total
    if (grepl("^guardrail_requests_total", line)) {
      value <- as.numeric(str_extract(line, "\\d+$"))
      metrics$total_requests <- metrics$total_requests + value
      metrics$sources[[group]]$total <- metrics$sources[[group]]$total + value
    }

    # Final request outcomes are independent of the number of detector hits.
    outcome_fields <- c(allowed = "approved_requests", blocked = "blocked_requests",
                        error = "service_errors", rejected = "rejected_requests",
                        cancelled = "cancelled_requests")
    if (grepl('^guardrail_request_outcomes_total', line)) {
      outcome <- str_match(line, 'outcome="([^"]+)"')[2]
      field <- unname(outcome_fields[outcome])
      value <- as.numeric(str_extract(line, "\\d+$"))
      if (length(field) == 1 && !is.na(field)) {
        metrics[[field]] <- metrics[[field]] + value
        metrics$sources[[group]][[outcome]] <- metrics$sources[[group]][[outcome]] + value
      }
    }
    if (grepl('^guardrail_active_requests', line)) {
      value <- as.numeric(str_extract(line, "\\d+$"))
      metrics$active_requests <- metrics$active_requests + value
      metrics$sources[[group]]$pending <- metrics$sources[[group]]$pending + value
    }

    # Parse guardrail_detections_by_detector
    if (grepl("^guardrail_detections_by_detector", line)) {
      detector_match <- str_match(line, 'detector="([^"]+)"')
      value_match <- str_extract(line, "\\d+$")

      if (!is.na(detector_match[2]) && !is.na(value_match)) {
        detector <- detector_match[2]
        value <- as.numeric(value_match)

        if (is.null(metrics$detections_by_detector[[detector]])) {
          metrics$detections_by_detector[[detector]] <- 0
        }
        metrics$detections_by_detector[[detector]] <-
          metrics$detections_by_detector[[detector]] + value
        previous <- metrics$source_detections[[group]][[detector]]
        metrics$source_detections[[group]][[detector]] <- if (is.null(previous)) value else previous + value
      }
    }
  }

  return(metrics)
}

# Fetch metrics from endpoint
fetch_metrics <- function() {
  tryCatch({
    response <- GET(METRICS_URL, timeout(10))
    if (status_code(response) == 200) {
      content_text <- content(response, "text", encoding = "UTF-8")
      return(parse_prometheus_metrics(content_text))
    } else {
      return(NULL)
    }
  }, error = function(e) {
    message("Error fetching metrics: ", e$message)
    return(NULL)
  })
}

# Stable business-policy groups; sums are detector hits, never blocked requests.
policy_hits <- function(detectors) {
  groups <- list(
    conduct = c("hap"),
    language = c("language", "language_detection", "language-detection"),
    injection = c("prompt_injection", "prompt-injection"),
    topic = c("regex_fruit", "regex-fruit", "regex_competitor", "regex-competitor", "topic_relevance", "topic-relevance")
  )
  vapply(groups, function(keys) sum(unlist(detectors[intersect(keys, names(detectors))])), numeric(1))
}

policy_rows <- function(detectors, available = TRUE, compact = FALSE, scale_max = NULL) {
  counts <- policy_hits(detectors)
  labels <- c(conduct = "Respectful language", language = "English only",
              injection = "No overrides", topic = "Lemons only")
  maximum <- if (is.null(scale_max)) max(c(1, counts)) else max(1, scale_max)
  div(class = paste("policy-rows", if (compact) "compact" else ""),
    lapply(names(counts), function(key) {
      div(class = paste("policy-row", key),
        div(class = "policy-label", labels[[key]]),
        div(class = "policy-track", `aria-hidden` = "true",
            div(class = "policy-fill", style = sprintf("width: %.2f%%", if (available) counts[[key]] / maximum * 100 else 0))),
        div(class = "policy-count live-value", if (available) format(counts[[key]], big.mark = ",") else "--"))
    }))
}

metric_card <- function(label, id, kind) {
  div(class = paste("metric-card", kind),
      div(class = "metric-label", label),
      div(class = "metric-value live-value", textOutput(id, inline = TRUE)))
}

# Each act has its own screen. Technical definitions stay behind a disclosure.
ui <- page_fluid(
  theme = bs_theme(bg = "#151515", fg = "#f5f5f5", primary = "#ee0000",
                   base_font = "system-ui", heading_font = "system-ui"),
  tags$head(
    tags$title("Lemonade Division · Live guardrails"),
    tags$style(HTML("
      :root { --paper:#151515; --panel:#202020; --line:#414141; --muted:#c7c7c7; --blue:#92c5f9; --green:#a9d792; --red:#ff8389; --purple:#c4b1ed; --gold:#f9df73; }
      * { box-sizing:border-box; } body { margin:0; background:var(--paper); font-family:'Red Hat Text','Helvetica Neue',Arial,sans-serif; }
      [hidden] { display:none!important; } .container-fluid { padding:0; }
      .stage { max-width:1920px; margin:auto; padding:22px clamp(22px,3vw,56px) 16px; border-top:5px solid #e00; }
      .masthead { display:flex; justify-content:space-between; align-items:center; gap:24px; margin-bottom:18px; }
      .brand { font-size:clamp(20px,1.65vw,30px); font-weight:600; letter-spacing:-.02em; }
      .brand small { font-size:14px; color:var(--muted); font-weight:400; margin-left:12px; }
      .toolbar { display:flex; align-items:center; gap:18px; } a { color:var(--blue); text-underline-offset:4px; }
      button { font:inherit; color:inherit; cursor:pointer; } .toolbar a,.toolbar button { font-size:15px; }
      .toolbar button { border:1px solid #777; padding:7px 12px; background:transparent; border-radius:3px; }
      button:focus-visible,a:focus-visible,summary:focus-visible { outline:3px solid var(--blue); outline-offset:4px; }
      .view-nav { display:flex; gap:8px; border-bottom:1px solid var(--line); margin-bottom:22px; }
      .view-nav button { background:transparent; border:0; border-bottom:4px solid transparent; padding:8px 18px 12px; font-size:20px; color:var(--muted); }
      .view-nav button[aria-pressed=true] { color:white; border-bottom-color:#e00; font-weight:600; }
      .view-heading { display:flex; align-items:center; justify-content:space-between; gap:20px; margin-bottom:20px; }
      h1 { font-family:'Red Hat Display','Helvetica Neue',Arial,sans-serif; font-size:clamp(32px,3vw,50px); font-weight:500; letter-spacing:-.025em; line-height:1.1; margin:0; }
      h2 { font-size:24px; font-weight:500; margin:0; } p { margin:0; }
      .view-heading p { color:var(--muted); font-size:18px; margin-top:8px; }
      .live-status { font-size:16px; padding:7px 12px; border:1px solid var(--line); border-radius:3px; white-space:nowrap; }
      .live-status.good { color:var(--green); } .live-status.bad { color:var(--red); }
      .metrics-grid { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:16px; margin-bottom:16px; }
      .metric-card { background:var(--panel); padding:20px 24px 16px; border-top:3px solid currentColor; }
      .metric-label { color:#e4e4e4; font-size:clamp(19px,1.6vw,26px); }
      .metric-value { font-size:clamp(64px,6.6vw,112px); font-weight:500; letter-spacing:-.045em; line-height:1.1; font-variant-numeric:tabular-nums; margin-top:10px; }
      .requests { color:var(--blue); } .allowed { color:var(--green); } .blocked { color:var(--red); } .errors { color:var(--gold); }
      .status-line { color:var(--muted); font-size:17px; margin-bottom:22px; }
      .policy-heading { display:flex; justify-content:space-between; align-items:baseline; gap:20px; margin:0 0 15px; }
      .policy-heading span { color:var(--muted); font-size:16px; }
      .policy-rows { display:grid; gap:12px; }
      .policy-row { display:grid; grid-template-columns:295px minmax(40px,1fr) 76px; align-items:center; gap:20px; }
      .policy-label { color:#ededed; font-size:clamp(21px,1.85vw,29px); }
      .policy-track { height:40px; background:#242424; border-radius:2px; overflow:hidden; }
      .policy-fill { height:100%; background:currentColor; transition:width .25s ease; }
      .policy-count { font-size:32px; line-height:1.1; font-weight:600; text-align:right; font-variant-numeric:tabular-nums; }
      .conduct { color:#f395a7; } .language { color:var(--blue); } .injection { color:var(--purple); } .topic { color:var(--gold); }
      .source-grid { display:grid; grid-template-columns:1fr 1fr; gap:24px; }
      .source-panel { background:var(--panel); border-top:4px solid var(--blue); padding:24px 28px; min-width:0; }
      .source-panel.automation { border-top-color:var(--purple); }
      .source-panel h2 { font-size:clamp(26px,2.4vw,38px); margin-bottom:18px; }
      .source-main { display:grid; grid-template-columns:1fr 1fr; gap:20px; margin-bottom:12px; }
      .source-main .metric-value { font-size:clamp(62px,6.2vw,108px); }
      .source-secondary { display:flex; gap:24px; flex-wrap:wrap; font-size:20px; margin:8px 0; }
      .source-secondary b { font-size:26px; margin-right:7px; }
      .source-rest { color:var(--muted); font-size:16px; padding-bottom:18px; border-bottom:1px solid var(--line); margin-bottom:18px; }
      .source-policy-label { font-size:16px; color:var(--muted); margin-bottom:12px; }
      .compact .policy-row { grid-template-columns:190px minmax(20px,1fr) 50px; gap:12px; }
      .compact .policy-label { font-size:18px; } .compact .policy-count { font-size:24px; } .compact .policy-track { height:26px; }
      .comparison-note { color:var(--muted); font-size:17px; margin-top:16px; }
      .stage-footer { display:flex; align-items:baseline; justify-content:space-between; gap:16px; color:var(--muted); font-size:14px; border-top:1px solid var(--line); margin-top:22px; padding-top:14px; }
      .definitions { margin-top:14px; color:var(--muted); font-size:15px; } .definitions summary { width:fit-content; cursor:pointer; color:var(--blue); }
      .definitions p { margin:10px 0; max-width:100ch; } .definitions pre { color:var(--muted); font-size:14px; white-space:pre-wrap; }
      .offline-warning { display:none; color:#fff; padding:12px 20px; background:#9b252b; font-size:20px; margin-bottom:14px; }
      .shiny-disconnected .offline-warning { display:block; } .shiny-disconnected .live-value,.shiny-disconnected .policy-fill,.shiny-disconnected .live-status { visibility:hidden; }
      .shiny-disconnected .source-rest,.shiny-disconnected .status-line { visibility:hidden; }
      @media(min-width:1600px) and (min-height:900px) { .stage { padding-top:30px; } .masthead { margin-bottom:24px; } .view-nav { margin-bottom:30px; } .view-heading { margin-bottom:30px; } .metric-card { padding:26px 30px; } .policy-track { height:52px; } .policy-rows { gap:18px; } .source-panel { padding:32px; } .compact .policy-track { height:38px; } .compact .policy-label { font-size:22px; } .compact .policy-row { grid-template-columns:240px minmax(20px,1fr) 60px; } .source-policy-label { font-size:18px; } }
      @media(min-width:761px) and (max-height:850px) { .stage { padding:16px 28px 12px; } .masthead { margin-bottom:10px; } .brand { font-size:22px; } .view-nav { margin-bottom:14px; } .view-nav button { font-size:18px; padding:6px 14px 8px; } .view-heading { margin-bottom:16px; } h1 { font-size:36px; } .view-heading p { font-size:16px; margin-top:6px; } .metric-card { padding:14px 20px 12px; } .metric-value { font-size:72px; margin-top:6px; } .metrics-grid { margin-bottom:12px; } .status-line { font-size:16px; margin-bottom:14px; } .policy-heading { margin-bottom:12px; } .policy-rows { gap:9px; } .policy-track { height:32px; } .policy-label { font-size:22px; } .policy-count { font-size:30px; } .stage-footer { margin-top:18px; padding-top:10px; } .definitions { margin-top:10px; } .source-panel { padding:20px 24px; } .source-panel h2 { margin-bottom:12px; } .source-main { margin-bottom:8px; } .source-main .metric-value { font-size:64px; } .source-panel h2 { font-size:26px; margin-bottom:10px; } .source-secondary { font-size:18px; margin:4px 0; } .source-secondary b { font-size:24px; } .source-rest { font-size:14px; padding-bottom:8px; margin-bottom:8px; } .source-policy-label { margin-bottom:8px; } .comparison-note { font-size:16px; margin-top:12px; } .compact .policy-track { height:26px; } .compact .policy-label { font-size:18px; } .compact .policy-count { font-size:24px; } }
      @media(max-width:1000px) { .brand small { display:block; margin:4px 0 0; } .policy-row { grid-template-columns:260px minmax(20px,1fr) 60px; gap:15px; } .source-panel { padding:20px; } .compact .policy-row { grid-template-columns:1fr 50px; gap:4px 10px; } .compact .policy-label { grid-column:1; } .compact .policy-count { grid-column:2; grid-row:1/3; } .compact .policy-track { grid-column:1; height:12px; } }
      @media(max-width:680px) { .stage { padding:18px; } .masthead { align-items:flex-start; } .toolbar { flex-wrap:wrap; justify-content:flex-end; gap:8px; } .toolbar a { font-size:14px; } .view-nav button { font-size:17px; padding:8px 12px 10px; } .view-heading { align-items:flex-start; flex-direction:column; gap:12px; } .view-heading p { font-size:16px; } .metrics-grid { grid-template-columns:1fr 1fr; gap:12px; } .metric-card { padding:15px; } .metric-value { font-size:56px; } .metric-label { font-size:17px; } .policy-row { grid-template-columns:1fr 60px; gap:5px 10px; } .policy-label { grid-column:1; font-size:20px; } .policy-track { grid-column:1; height:22px; } .policy-count { grid-column:2; grid-row:1/3; } .policy-heading { align-items:flex-start; flex-direction:column; gap:6px; } .source-grid { grid-template-columns:1fr; } .source-main .metric-value { font-size:64px; } .stage-footer { flex-direction:column; gap:5px; } .status-line { font-size:15px; } }
      @media(prefers-reduced-motion:reduce) { .policy-fill { transition:none; } }
    ")),
    tags$script(HTML("
      document.addEventListener('DOMContentLoaded', function() {
        const buttons = Array.from(document.querySelectorAll('[data-view]'));
        function showView() {
          const view = location.hash === '#red-team' ? 'red-team' : 'agentops';
          document.querySelectorAll('[data-screen]').forEach(function(screen) { screen.hidden = screen.dataset.screen !== view; });
          buttons.forEach(function(button) { button.setAttribute('aria-pressed', String(button.dataset.view === view)); });
          window.dispatchEvent(new Event('resize'));
        }
        buttons.forEach(function(button) { button.addEventListener('click', function() { location.hash = button.dataset.view; showView(); }); });
        window.addEventListener('hashchange', showView); showView();
        const full = document.getElementById('fullscreen');
        full.addEventListener('click', async function() {
          try { if (document.fullscreenElement) await document.exitFullscreen(); else await document.documentElement.requestFullscreen(); }
          catch (_) { full.textContent = 'Use browser full screen'; }
        });
        document.addEventListener('fullscreenchange', function() { full.textContent = document.fullscreenElement ? 'Exit full screen' : 'Full screen'; });
      });
    "))
  ),
  div(class = "stage",
    div(class = "masthead",
      div(class = "brand", "[Customer] Lemonade Division", tags$small("Demo scenario")),
      div(class = "toolbar",
        if (grepl("^https://[A-Za-z0-9.-]+(?::[0-9]+)?/[^?#]*$", CONTROL_URL, perl = TRUE))
          tags$a(href = CONTROL_URL, target = "_blank", rel = "noopener", "Operator controls ↗"),
        tags$button(id = "fullscreen", type = "button", "Full screen"))),
    tags$nav(class = "view-nav", `aria-label` = "Stage views",
      tags$button(type = "button", `data-view` = "agentops", `aria-controls` = "agentops-view", `aria-pressed` = "true", "01 · AgentOps"),
      tags$button(type = "button", `data-view` = "red-team", `aria-controls` = "red-team-view", `aria-pressed` = "false", "02 · Red teaming")),
    div(class = "offline-warning", role = "alert", "Connection lost · live values hidden"),
    tags$section(id = "agentops-view", `data-screen` = "agentops", `aria-labelledby` = "agentops-title",
      div(class = "view-heading",
        div(h1(id = "agentops-title", "Guardrails in action"), p("One assistant. Four business rules.")), uiOutput("feed_status")),
      div(class = "metrics-grid",
        metric_card("Requests", "total_requests", "requests"),
        metric_card("Allowed", "approved_requests", "allowed"),
        metric_card("Blocked", "blocked_requests", "blocked"),
        metric_card("Service errors", "service_errors", "errors")),
      div(class = "status-line", textOutput("request_status")),
      div(class = "policy-heading", h2("Policy checks triggered"), tags$span("Detector hits · a request may trigger several")),
      uiOutput("detector_bars")),
    tags$section(id = "red-team-view", `data-screen` = "red-team", hidden = "hidden", `aria-labelledby` = "red-team-title",
      div(class = "view-heading",
        div(h1(id = "red-team-title", "Audience vs. Red Team"), p("Same protected assistant. Two ways to test it.")), uiOutput("comparison_status")),
      uiOutput("source_comparison"),
      p(class = "comparison-note", "Request outcomes, not attack success. Different prompt mixes; presenter requests excluded.")),
    div(class = "stage-footer",
      tags$span("Live process totals · reset on app restart"),
      textOutput("last_updated", inline = TRUE), tags$span("Powered by OpenShift AI")),
    tags$details(class = "definitions", tags$summary("How to read these numbers"),
      p("Requests = allowed + blocked + service errors + rejected + cancelled + pending. Rejections include admission and length limits. An allowed answer can still safely refuse an attack."),
      p("Policy bars count detector hits, including multiple hits on one request. Bar lengths use one shared scale across the two comparison panels. The four business rules group related detectors; full detector counts appear below."),
      p("Audience includes all three suggestion roles. Current-process counters are separate from saved campaign reports. Review findings in Operator controls before calling an attack successful."),
      tags$pre(textOutput("detector_details", inline = TRUE)))
  )
)

server <- function(input, output, session) {
  metrics_data <- reactiveVal(NULL)
  last_success <- reactiveVal(NULL)
  observe({
    invalidateLater(REFRESH_INTERVAL * 1000, session)
    new_metrics <- fetch_metrics()
    metrics_data(new_metrics)
    if (!is.null(new_metrics)) last_success(Sys.time())
  })

  fields <- c(total_requests = "total_requests", approved_requests = "approved_requests",
              blocked_requests = "blocked_requests", service_errors = "service_errors")
  for (name in names(fields)) local({
    id <- name; field <- fields[[name]]
    output[[id]] <- renderText({
      m <- metrics_data()
      if (is.null(m)) "--" else format(m[[field]], big.mark = ",")
    })
  })
  status_badge <- function() {
    if (is.null(metrics_data())) div(class = "live-status bad", "Data unavailable")
    else div(class = "live-status good", "● Live · protected")
  }
  output$feed_status <- renderUI(status_badge())
  output$comparison_status <- renderUI(status_badge())
  output$request_status <- renderText({
    m <- metrics_data()
    if (is.null(m)) return("Live values hidden until metrics recover")
    sprintf("%s pending  |  %s rejected  |  %s cancelled", m$active_requests, m$rejected_requests, m$cancelled_requests)
  })
  output$detector_bars <- renderUI({
    m <- metrics_data()
    policy_rows(if (is.null(m)) list() else m$detections_by_detector, !is.null(m))
  })
  output$source_comparison <- renderUI({
    m <- metrics_data(); available <- !is.null(m)
    comparison_max <- if (available) max(c(1, policy_hits(m$source_detections$audience), policy_hits(m$source_detections$automation))) else 1
    source_card <- function(key, title) {
      values <- if (available) m$sources[[key]] else empty_source()
      show <- function(field) if (available) format(values[[field]], big.mark = ",") else "--"
      div(class = paste("source-panel", key), h2(title),
        div(class = "source-main",
          div(class = "requests", div(class = "metric-label", "Requests"), div(class = "metric-value live-value", show("total"))),
          div(class = "blocked", div(class = "metric-label", "Blocked"), div(class = "metric-value live-value", show("blocked")))),
        div(class = "source-secondary",
          tags$span(class = "allowed", tags$b(class = "live-value", show("allowed")), "allowed"),
          tags$span(class = "errors", tags$b(class = "live-value", show("error")), "service errors")),
        div(class = "source-rest", sprintf("%s pending | %s rejected | %s cancelled", show("pending"), show("rejected"), show("cancelled"))),
        p(class = "source-policy-label", "Policy checks triggered · detector hits"),
        policy_rows(if (available) m$source_detections[[key]] else list(), available, compact = TRUE, scale_max = comparison_max))
    }
    div(class = "source-grid", source_card("audience", "The audience"), source_card("automation", "Automated Red Team"))
  })
  output$detector_details <- renderText({
    m <- metrics_data()
    if (is.null(m)) return("Live data unavailable")
    if (!length(m$detections_by_detector)) return("No detector hits yet")
    paste(names(m$detections_by_detector), unlist(m$detections_by_detector), sep = ": ", collapse = "\n")
  })
  output$last_updated <- renderText({
    stamp <- last_success()
    if (is.null(stamp)) "Waiting for live metrics" else paste("Last update", format(stamp, "%H:%M:%S UTC", tz = "UTC"))
  })
  # Both stage views keep refreshing even while one is hidden.
  for (id in c(names(fields), "feed_status", "comparison_status", "request_status", "detector_bars", "source_comparison"))
    outputOptions(output, id, suspendWhenHidden = FALSE)
}

shinyApp(ui = ui, server = server)
