---
title: Work Permit System — reference index (no reproduced text)
standard: OISD-STD-105
issuer: Oil Industry Safety Directorate, Ministry of Petroleum & Natural Gas (India)
revision: Revision I, September 2004
provenance: REFERENCE_ONLY
official_text: false
licence: >
  OISD publications are the property of the Ministry of Petroleum & Natural Gas and are
  marked FOR RESTRICTED CIRCULATION. They "shall not be reproduced or copied or loaned or
  exhibited to others without written consent from OISD". The standard text is therefore
  NOT included in this repository.
obtain_from: https://www.oisd.gov.in/
local_override: data/regulations_local/  (git-ignored; place your licensed copy there)
---

# OISD-STD-105 — Work Permit System (reference index)

> **This file deliberately contains no text from the standard.**
> OISD-STD-105 is a restricted-circulation document whose reproduction requires written
> consent from OISD. Publishing it in a public repository would breach that condition.
> What follows is a *navigational index* — section names and the topics they govern — so
> the assistant can cite the correct clause location and tell an operator where to look.
> To make answers substantive, place your organisation's licensed copy in
> `data/regulations_local/` (git-ignored); the retriever loads it automatically and
> upgrades these citations to `provenance: OFFICIAL`.

## Applicability

Applies to work permit systems at hydrocarbon processing, handling and storage
installations under the Ministry of Petroleum & Natural Gas. Implementation is treated as
mandatory at petroleum handling facilities; absence of a functioning permit system is a
major non-conformance at audit.

## Permit categories governed by the standard

| Permit type | Governs |
|---|---|
| **Cold work** | Non-spark-producing work in or near hydrocarbon facilities |
| **Hot work** | Any work introducing an ignition source — welding, cutting, grinding, open flame |
| **Confined space entry** | Entry into vessels, tanks, pits, sewers and similar enclosed spaces |
| **Electrical isolation / energisation** | Isolation, lock-out and re-energisation of electrical equipment |

## Topics to consult in the standard

- **Gas testing** — measurement of combustible gas as **% LEL**, toxic gas in **ppm**, and
  **oxygen as % by volume**; when initial testing is required and at what intervals
  re-testing or continuous monitoring applies.
- **Hot work conditions** — the atmospheric limits that must be satisfied before an
  ignition source is permitted, isolation/blanking of hydrocarbon sources, fire-watch
  requirements, and the conditions that mandate immediate suspension of work.
- **Confined space entry** — oxygen range, positive isolation, purging and ventilation,
  standby person, communication and rescue arrangements.
- **Simultaneous operations** — cross-checking of concurrent permits in a shared area,
  where individually-safe activities become unsafe in combination.
- **Issue, validity, extension and closure** — authorised signatories, scope and time
  limits, revalidation, and the effect of any change in conditions.
- **Shift handover** — communication of open-permit status to the incoming crew.

## How SentinelAI cites this standard

The rule engine (`sentinel/rules/engine.py`) references this standard by **section name**,
never by reproduced text or invented clause number. All numeric gas/oxygen thresholds used
in code are **site-configurable engineering defaults**, deliberately conservative, and must
be set by each plant from its own permit conditions and its licensed copy of the standard.
They are not represented as quoted legal limits.
