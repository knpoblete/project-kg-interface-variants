// Self-identification roster for the session start screen. The prescreening
// questionnaire (mockups/prescreening.csv) was anonymous, so there's no way
// to know in advance which real participant is which P<n> -- instead, the
// participant picks their own CURRENT role (Q6 in the questionnaire) from
// this list at the start of the session, and that choice sets ?participant=
// going forward. This is deliberately the CURRENT role, not the
// aspirational target role shown once the session starts (e.g. "Consulting
// Technical Manager", not "Consulting Director") -- a participant recognizes
// their own current job title far more reliably than an abstract goal-role
// label. D0 (facilitator demo) is intentionally left out of this picker and
// stays reachable only via an explicit ?participant=D0 link.
//
// P5 (Project Manager, nonprofit) and P6 (Group Controller/Consultant, real
// estate and accounting) DROPPED OUT before their sessions ran and are
// removed from this list so neither can be started by mistake -- their
// generated data still exists and is still previewable in the test
// prototype, it just can't be run as a session.
//
// New recruits are appended, never inserted earlier, so an existing
// participant's ?participant= link never changes meaning.

const PARTICIPANT_ROSTER = [
  { id: "P1", currentRole: "Consulting Technical Manager", industry: "ERP Software" },
  { id: "P2", currentRole: "DevOps Engineer", industry: "IT / Electrical Signal Analysis" },
  { id: "P3", currentRole: "Marketing Analytics Manager", industry: "Hospitality" },
  { id: "P4", currentRole: "Engineering Manager", industry: "IT and Software" },
  { id: "P7", currentRole: "Product Analyst", industry: "Fintech" },
  { id: "P8", currentRole: "Functional Consultant Level 3", industry: "Software Consultancy" },
  { id: "P9", currentRole: "Research Coordinator", industry: "Wildlife Conservation" },
  { id: "P10", currentRole: "Monitoring, Evaluation, and Learning Officer", industry: "Tamaraw Conservation" },
  { id: "P11", currentRole: "Manager (Individual Contributor)", industry: "Pharmaceutical Industry" },
];
