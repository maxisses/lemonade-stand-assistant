/* Public presentation links only. Never add credentials or access tokens. */
window.LEMONADE_DECK = {
  "customer": "[Customer]",
  "eventDate": "17 November 2026",
  "presenter": "Max Dargatz · Red Hat",
  "links": {
    "chat": "https://lemonade-chat-lemonade-demo.apps.rosa.lemonade-demo.28s8.p3.openshiftapps.com",
    "dashboard": "https://lemonade-dashboard-lemonade-demo.apps.rosa.lemonade-demo.28s8.p3.openshiftapps.com",
    "control": "https://lemonade-chat-lemonade-demo.apps.rosa.lemonade-demo.28s8.p3.openshiftapps.com/control",
    "audience": "https://lemonade-audience-lemonade-demo.apps.rosa.lemonade-demo.28s8.p3.openshiftapps.com/join",
    "console": "https://console-openshift-console.apps.rosa.lemonade-demo.28s8.p3.openshiftapps.com",
    "ai": "https://rh-ai.apps.rosa.lemonade-demo.28s8.p3.openshiftapps.com",
    "source": "https://github.com/maxisses/lemonade-stand-assistant"
  },
  "readiness": {
    "chat": "Existing authenticated route; sign in before presenting.",
    "dashboard": "Existing authenticated route; sign in before presenting.",
    "control": "Deployed at fa5f23f, Synced/Healthy. Saved custom Functional profile, immutable run snapshot, idempotent start and audience-open settings lock passed serial live checks on 28 October 2026.",
    "audience": "Direct chat, same-session quota retention and real SSE progress then validated content passed serial live checks at fa5f23f. Audience closed afterward. Physical QR and capacity rehearsal remain pending."
  },
  "validation": {
    "presentation": "18 slides visually reviewed; local assets and configured QR verified.",
    "liveIntegration": "Initial campaigns remain historical evidence. fa5f23f passed a saved custom Functional profile: 2 allowed, 1 blocked, 0 errors; 3 new target generations total across the small check, all qwen38-27b at concurrency 1.",
    "eventCapacity": "Pending an agreed bounded rehearsal; configured limits are not measured capacity.",
    "audienceUxRevision": "Verified serially: direct chat entry, legacy role fields ignored with session/quota retained, allowed SSE status then validated content, blocked SSE with no answer content.",
    "settingsScope": "Concurrency 1–4 and advertised model selection are implemented. No live concurrency above 1 or alternative-model inference validated; catalogue currently contains only qwen38-27b.",
    "currentRestart": "Passed at fa5f23f: saved profile, run snapshot, model and concurrency retained after controlled app/provider restart; audience closed. All 12 deployments ready and both GitOps applications Synced/Healthy."
  }
};
