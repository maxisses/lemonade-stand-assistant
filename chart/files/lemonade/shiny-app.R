library(shiny)
library(httr)
library(stringr)
library(bslib)

# Configuration
METRICS_URL <- Sys.getenv("METRICS_URL", "http://lemonade-stand:8080/metrics")
REFRESH_INTERVAL <- as.integer(Sys.getenv("REFRESH_INTERVAL", "1")) # seconds

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
    detections_by_detector = list()
  )

  for (line in lines) {
    # Skip comments and empty lines
    if (grepl("^#", line) || nchar(trimws(line)) == 0) next

    # Parse guardrail_requests_total
    if (grepl("^guardrail_requests_total", line)) {
      value <- as.numeric(str_extract(line, "\\d+$"))
      metrics$total_requests <- metrics$total_requests + value
    }

    # Final request outcomes are independent of the number of detector hits.
    outcome_fields <- c(allowed = "approved_requests", blocked = "blocked_requests",
                        error = "service_errors", rejected = "rejected_requests")
    if (grepl('^guardrail_request_outcomes_total', line)) {
      outcome <- str_match(line, 'outcome="([^"]+)"')[2]
      field <- outcome_fields[[outcome]]
      if (!is.null(field)) metrics[[field]] <- metrics[[field]] + as.numeric(str_extract(line, "\\d+$"))
    }
    if (grepl('^guardrail_active_requests', line)) {
      metrics$active_requests <- metrics$active_requests + as.numeric(str_extract(line, "\\d+$"))
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

# UI
ui <- page_fluid(
  theme = bs_theme(
    bg = "#151515",
    fg = "#FFFFFF",
    primary = "#EE0000",  # Red Hat Red
    secondary = "#FFFFFF",
    base_font = "system-ui",
    heading_font = "system-ui"
  ),

  tags$head(
    tags$style(HTML("
      body {
        background: #151515;
      }
      .metric-card {
        background: #1F1F1F;
        border-radius: 3px;
        border-left: 4px solid #EE0000;
        padding: 20px;
        text-align: center;
        box-shadow: 0 1px 3px rgba(0,0,0,0.3);
        margin: 10px;
        height: 150px;
        display: flex;
        flex-direction: column;
        justify-content: center;
      }
      .metric-value {
        font-size: 48px;
        font-weight: bold;
        margin: 10px 0;
        color: #FFFFFF;
      }
      .metric-label {
        font-size: 18px;
        color: #C9C9C9;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        font-weight: 600;
      }
      .total { color: #EE0000; }  /* Red Hat Red */
      .blocked-input { color: #A30000; }  /* Red Hat Dark Red */
      .blocked-output { color: #A30000; }  /* Red Hat Dark Red */
      .approved { color: #3E8635; }  /* Red Hat Green */
      .detector-bar {
        background: #2A2A2A;
        border-radius: 4px;
        padding: 10px;
        margin: 5px 0;
        color: white;
        font-weight: bold;
        text-align: left;
        position: relative;
        overflow: hidden;
      }
      .detector-bar::before {
        content: '';
        position: absolute;
        left: 0;
        top: 0;
        bottom: 0;
        width: var(--width);
        z-index: 0;
        transition: width 0.3s ease;
      }
      .detector-bar > * {
        position: relative;
        z-index: 1;
      }
      .detector-hap::before { background: #EE0000; }  /* Red Hat Red */
      .detector-language::before { background: #0066CC; }  /* Red Hat Blue */
      .detector-prompt_injection::before, .detector-prompt-injection::before { background: #8461C9; }  /* Red Hat Purple */
      .detector-regex_fruit::before, .detector-regex_competitor::before, .detector-regex-fruit::before, .detector-regex-competitor::before { background: #F0AB00; }  /* Red Hat Gold */
      .detector-regex_fruit, .detector-regex_competitor, .detector-regex-fruit, .detector-regex-competitor { color: #151515; }  /* Dark text on gold */
      .detector-pii::before { background: #EC7A08; }  /* Red Hat Orange */
      .detector-message_length::before, .detector-message-length::before { background: #6A6E73; }  /* Red Hat Gray */
      .detector-topic_relevance::before, .detector-topic-relevance::before { background: #3E8635; }  /* Red Hat Green */
      .detector-language-detection::before, .detector-language_detection::before { background: #009596; }  /* Red Hat Cyan */
      h2 {
        margin-top: 40px;
        margin-bottom: 10px;
        color: #FFFFFF;
        font-weight: 700;
        border-left: 4px solid #EE0000;
        padding-left: 10px;
      }
      .last-updated {
        text-align: right;
        margin: 10px 0;
        font-size: 12px;
        color: #C9C9C9;
      }
      .subtitle {
        text-align: center;
        color: #C9C9C9;
        font-size: 16px;
        margin-top: -10px;
        margin-bottom: 20px;
      }
      .bslib-grid {
        margin-bottom: 30px;
      }
      .footer {
        text-align: center;
        color: #6A6E73;
        font-size: 18px;
        margin-top: 30px;
        padding: 20px 0;
        border-top: 1px solid #2A2A2A;
      }
    "))
  ),

  titlePanel("🍋 [Customer] Lemonade Division"),

  div(class = "subtitle", "Demo scenario • Act 1: AgentOps • Protected assistant"),

  layout_columns(
    col_widths = c(3, 3, 3, 3),
    fill = FALSE,

    div(class = "metric-card",
        div(class = "metric-label", "Conversations"),
        div(class = "metric-value total", textOutput("total_requests"))
    ),

    div(class = "metric-card",
        div(class = "metric-label", "Blocked requests"),
        div(class = "metric-value blocked-input", textOutput("blocked_requests"))
    ),

    div(class = "metric-card",
        div(class = "metric-label", "Service errors"),
        div(class = "metric-value blocked-output", textOutput("service_errors"))
    ),

    div(class = "metric-card",
        div(class = "metric-label", "Approved responses"),
        div(class = "metric-value approved", textOutput("approved_requests"))
    )
  ),

  div(class = "subtitle", textOutput("request_status")),
  h2("Policy checks triggered"),
  p("One request can trigger several checks. These hits are separate from request outcomes."),
  uiOutput("detector_bars"),

  div(class = "last-updated", textOutput("last_updated")),

  div(class = "footer", "Live application metrics • Counters reset when the application restarts • Powered by OpenShift AI")
)

# Server
server <- function(input, output, session) {

  # Reactive value to store metrics
  metrics_data <- reactiveVal(NULL)
  last_success <- reactiveVal(NULL)

  # Auto-refresh metrics
  observe({
    invalidateLater(REFRESH_INTERVAL * 1000, session)

    new_metrics <- fetch_metrics()
    metrics_data(new_metrics)
    if (!is.null(new_metrics)) last_success(Sys.time())
  })

  # Render metric cards
  output$total_requests <- renderText({
    m <- metrics_data()
    if (is.null(m)) return("--")
    format(m$total_requests, big.mark = ",")
  })

  output$blocked_requests <- renderText({
    m <- metrics_data()
    if (is.null(m)) return("--")
    format(m$blocked_requests, big.mark = ",")
  })

  output$service_errors <- renderText({
    m <- metrics_data()
    if (is.null(m)) return("--")
    format(m$service_errors, big.mark = ",")
  })

  output$approved_requests <- renderText({
    m <- metrics_data()
    if (is.null(m)) return("--")
    format(m$approved_requests, big.mark = ",")
  })

  output$request_status <- renderText({
    m <- metrics_data()
    if (is.null(m)) return("Live data unavailable")
    paste("Pending:", m$active_requests, "| Admission/length rejections:", m$rejected_requests,
          "| Source: presenter | Mode: protected")
  })

  # Render detector bars
  output$detector_bars <- renderUI({
    m <- metrics_data()
    if (is.null(m) || length(m$detections_by_detector) == 0) {
      return(div("No detections yet"))
    }

    # Sort by count descending
    detectors <- m$detections_by_detector
    detectors_sorted <- detectors[order(unlist(detectors), decreasing = TRUE)]

    # Find max value for scaling
    max_val <- max(unlist(detectors_sorted))
    if (max_val == 0) max_val <- 1

    # Create bars
    bars <- lapply(names(detectors_sorted), function(detector) {
      count <- detectors_sorted[[detector]]
      width_pct <- (count / max_val) * 100

      # Map detector names to display names
      display_name <- switch(detector,
                             "hap" = "Respectful language",
                             "language" = "🇬🇧 Non-English",
                             "language_detection" = "🇬🇧 Non-English",
                             "prompt_injection" = "👮 Instruction override",
                             "regex_fruit" = "🍋 Lemon-only topics",
                             "regex_competitor" = "🍋 Lemon-only topics",
                             "pii" = "🔒 PII",
                             "message_length" = "📏 Length",
                             "topic_relevance" = "🍑 Off-Topic",
                             detector)

      div(
        class = paste0("detector-bar detector-", gsub("_", "-", detector)),
        style = paste0("--width: ", width_pct, "%;"),
        tags$span(sprintf("%s: %s", display_name, format(count, big.mark = ",")))
      )
    })

    do.call(tagList, bars)
  })

  # Last updated timestamp
  output$last_updated <- renderText({
    stamp <- last_success()
    if (is.null(stamp)) return("Waiting for live metrics")
    paste("Last successful update (UTC):", format(stamp, "%H:%M:%S", tz = "UTC"))
  })
}

# Run app
shinyApp(ui = ui, server = server)
