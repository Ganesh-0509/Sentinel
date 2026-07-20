---
title: Mine gas monitoring, permissible limits and safety interlocks
standard: Coal Mines Regulations 2017 (DGMS)
issuer: Directorate General of Mines Safety, Ministry of Labour & Employment, Government of India
enabling_act: The Mines Act, 1952
provenance: STATUTE
official_text: false
sources:
  - https://www.dgms.gov.in/  (DGMS circulars index)
  - https://www.dgms.net/Coal%20Mines%20Regulation%202017.pdf
  - https://www.dgms.gov.in/writereaddata/UploadFile/DGMScircularsfrom20182024_06122024.pdf
note: >
  Statutory limits and classifications restated from the Coal Mines Regulations 2017 and
  DGMS circulars. Figures are accurate as sourced but this is a condensed restatement,
  not the gazette text. Verify against the official publication before operational or
  legal use.
---

# DGMS — mine gas monitoring and permissible limits

## Scope and authority

The Directorate General of Mines Safety (DGMS), under the Ministry of Labour and
Employment, administers safety in mines under the Mines Act, 1952. For coal mines the
operative subordinate legislation is the **Coal Mines Regulations 2017 (CMR-2017)**.
DGMS additionally issues **circulars** — technical, legislative and general — which
clarify procedures for gas monitoring, equipment approval, accident reporting, appointment
of officials and inspection.

This corpus entry exists because a compound-risk layer deployed in Indian heavy industry
will encounter both **factory** jurisdiction (Factories Act, 1948) and **mine**
jurisdiction (Mines Act / CMR-2017). The gas thresholds and interlock duties differ, and
applying the wrong regime is itself a compliance failure.

## Permissible methane concentrations

| Location / condition | Limit |
|---|---|
| General body of air at any place in the mine | **not exceeding 1.25 % CH₄** |
| Return airways | **not exceeding 0.75 % CH₄** |

Methane is lighter than air and accumulates at the roof, so sampling location materially
affects the reading — the same failure mode this platform addresses in a plant setting,
where a single point sensor may not represent the true zone hazard.

## Explosive range

Methane is flammable in air over approximately the **5 % to 15 %** concentration range.
Statutory action limits are set an order of magnitude below the lower flammable limit
precisely so that control action occurs long before the mixture becomes explosive.

## Classification of gassy seams

Seams are graded by the rate of methane emission, with detection thresholds triggering
progressively stricter controls:

| Degree | Indicative methane threshold |
|---|---|
| Degree I (gassy) | 0.1 % |
| Degree II | 0.5 % |
| Degree III | 1.25 % |

## Automatic interlocks

Where diesel-powered equipment operates underground, the installation is required to
provide automatic protection: **power cut-off when methane exceeds 0.75 %**, and when
noxious gas exceeds **50 ppm**, together with an automatic alarm.

This is a statutory example of the principle the SentinelAI rule engine implements: a hard
interlock that acts deterministically, without waiting for human judgement or model
inference.

## Threshold limit values for other gases

| Gas | Threshold limit value |
|---|---|
| Carbon monoxide (CO) | 0.005 % (50 ppm) |
| Carbon dioxide (CO₂) | 0.5 % |
| Hydrogen sulphide (H₂S) | 0.0005 % (5 ppm) |
| Nitric oxide (NO) | 0.0025 % (25 ppm) |
| Nitrogen dioxide (NO₂) | 0.0005 % (5 ppm) |
| Oxygen (O₂) | not less than 19 % |

## Continuous monitoring and telemonitoring

DGMS guidance covers the use and maintenance of **telemonitoring systems** and **local
methane detectors** in underground coal mines: environmental parameters are monitored
continuously, with alarms annunciated to a surface control room, and detectors are subject
to defined calibration and maintenance intervals. Detector drift and calibration lapse are
recognised failure modes — a monitoring system is only as trustworthy as its last
calibration.

## Relevance to compound risk monitoring

1. **Thresholds sit far below the explosive range.** Statutory limits are set so that
   action is possible while the situation is still recoverable, which is the same logic as
   forecasting a threshold crossing rather than reacting to it.
2. **Automatic cut-off is mandated, not advised.** Where the hazard is well understood, the
   law requires a deterministic interlock. This supports the design choice that hard limits
   hold veto authority over any model output.
3. **Sampling location determines the reading.** Methane stratifies at the roof; a detector
   placed elsewhere under-reads the true hazard. This is the mine-sector analogue of the
   attenuated point sensor this platform is built to compensate for.
4. **Calibration and maintenance are compliance obligations**, which is why sensor drift is
   treated here as a monitored anomaly rather than an inconvenience.
