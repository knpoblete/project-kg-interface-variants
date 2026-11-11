// Self-identification roster for the pilot start screen. The prescreening
// questionnaire (mockups/prescreening.csv) was anonymous, so there's no way
// to know in advance which real participant is P1-P5 -- instead, the
// participant picks their own CURRENT role (Q6 in the questionnaire) from
// this list at the start of the session, and that choice sets ?participant=
// going forward. This is deliberately the CURRENT role, not the
// aspirational target role shown once the session starts (e.g. "Consulting
// Technical Manager", not "Consulting Director") -- a participant recognizes
// their own current job title far more reliably than an abstract goal-role
// label. D0 (facilitator demo) and P6-P9 (not yet recruited) are
// intentionally left out of this picker; D0 stays reachable only via an
// explicit ?participant=D0 link.

const PARTICIPANT_ROSTER = [
  { id: "P1", currentRole: "Consulting Technical Manager", industry: "ERP Software" },
  { id: "P2", currentRole: "DevOps Engineer", industry: "IT / Electrical Signal Analysis" },
  { id: "P3", currentRole: "Marketing Analytics Manager", industry: "Hospitality" },
  { id: "P4", currentRole: "Engineering Manager", industry: "IT and Software" },
  { id: "P5", currentRole: "Project Manager", industry: "Nonprofit" },
];
