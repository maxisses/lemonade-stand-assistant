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
    "control": "Implemented operator UI and API: Start, Pause, Resume, Stop, Review, Retest and report export. Live deployment and real OpenShift authorization validated on 28 October 2026.",
    "audience": "Implemented role selection and bounded chat; access defaults to closed and closes after restart. Live route and role/session flow validated on 28 October 2026. Physical phone/QR and event-capacity rehearsal remain pending."
  },
  "validation": {
    "presentation": "18 slides visually reviewed; local assets and configured QR verified.",
    "liveIntegration": "Validated on 28 October 2026: six-case functional run, nine-case adaptive run, selected-case retest and bounded audience flow.",
    "eventCapacity": "Pending an agreed bounded rehearsal; configured limits are not measured capacity."
  }
};
