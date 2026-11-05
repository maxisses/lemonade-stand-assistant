/* Public presentation links only. Never add credentials or access tokens. */
window.LEMONADE_DECK = {
  "customer": "Snemeis",
  "eventDate": "17 November 2026",
  "presenter": "Max Dargatz · Red Hat",
  "links": {
    "chat": "https://lemonade-chat-lemonade-demo.apps.rosa.lemonade-demo.6abk.p3.openshiftapps.com",
    "dashboard": "https://lemonade-dashboard-lemonade-demo.apps.rosa.lemonade-demo.6abk.p3.openshiftapps.com",
    "control": "https://lemonade-chat-lemonade-demo.apps.rosa.lemonade-demo.6abk.p3.openshiftapps.com/control",
    "audience": "https://lemonade-audience-lemonade-demo.apps.rosa.lemonade-demo.6abk.p3.openshiftapps.com/join",
    "console": "https://console-openshift-console.apps.rosa.lemonade-demo.6abk.p3.openshiftapps.com",
    "ai": "https://rh-ai.apps.rosa.lemonade-demo.6abk.p3.openshiftapps.com",
    "source": "https://github.com/maxisses/lemonade-stand-assistant"
  },
  "readiness": {
    "chat": "Rebuilt 4 November 2026: authenticated HTTPS and one short protected benign response passed. Sign in before presenting.",
    "dashboard": "Rebuilt 4 November 2026: authenticated HTTPS and WebSocket upgrade passed. Counters cover the current process.",
    "control": "Rebuilt 4 November 2026: six reports and one saved profile restored; idle, qwen38-27b, concurrency 1. Earlier campaign evaluations remain historical.",
    "audience": "New QR and /join URL configured. Chat page and closed admission verified; operator paths denied. Audience closed; physical QR and capacity rehearsal pending."
  },
  "validation": {
    "presentation": "18 slides visually reviewed; local assets and configured QR verified.",
    "liveIntegration": "Initial campaigns remain historical evidence. fa5f23f passed a saved custom Functional profile: 2 allowed, 1 blocked, 0 errors; 3 new target generations total across the small check, all qwen38-27b at concurrency 1.",
    "eventCapacity": "Pending an agreed bounded rehearsal; configured limits are not measured capacity.",
    "audienceUxRevision": "Verified serially: direct chat entry, legacy role fields ignored with session/quota retained, allowed SSE status then validated content, blocked SSE with no answer content.",
    "settingsScope": "Concurrency 1–4 and advertised model selection are implemented. No live concurrency above 1 or alternative-model inference validated; catalogue currently contains only qwen38-27b.",
    "currentRestart": "Passed at fa5f23f: saved profile, run snapshot, model and concurrency retained after controlled app/provider restart; audience closed. All 12 deployments ready and both GitOps applications Synced/Healthy.",
    "currentRebuild": "Passed on 4 November 2026: 12 deployments ready, restored records verified, authenticated routes/WebSocket and public boundaries checked; 3 serial probes passed (benign, topic, language). No new campaign or load test."
  }
};
