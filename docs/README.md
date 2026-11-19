# Documents

Start with the [project summary](../README.md), the [research report](../results/report.md) and the [contributions page](contributions.md). The pages below hold the designs, protocols and results behind each claim, grouped by question. Pages marked *protocol* were committed before the outcomes they test were opened.

## 1. Replicating the paper

| Page | Question |
|---|---|
| [Implementation](algorithm.md) | How are BASL and Bayesian evaluation implemented? |
| [Simulation](simulation.md) | Does the synthetic acceptance loop reproduce Figure 2? |
| [Hard-cutoff sensitivity](hard-selection.md) | Do the public-data conclusions change under strong selection? |
| [Selection strength and audit](selection-strength.md) · [Protocol](selection-strength-protocol.md) *protocol* | When does reject inference work, and can a small random audit of rejects repair it? |
| [Calendar forecasts](vintages.md) | Does better historical measurement improve next-quarter forecasts? |
| [Deviations](deviations.md) | Where and why does the replication differ from the paper? |

## 2. Which outcomes decide a lending policy

| Page | Question |
|---|---|
| [Policy information](policy-information.md) | Which outcome totals identify every comparison among five cutoffs? |
| [Identification](identification.md) | Can identical visible data support opposite decisions? |
| [Policy bounds](bounds.md) | How wrong may the reject prior be before an expansion loses its case? |
| [Decision audit](decision-audit.md) | How many hidden outcomes settle a proposed expansion? |
| [Philippine offers](rct.md) | What does a real randomized credit offer identify? |

## 3. Lending to learn

| Page | Question |
|---|---|
| [Exploration](exploration.md) · [Information value](information-value.md) · [Dependence bounds](pilot-dependence.md) | When can one loss-making pilot pay for its information? |
| [SBA replay](pilot-replay.md) · [SBA 7(a) transfer](pilot-transfer.md) · [Targeting](pilot-targeting.md) | Does the rule change decisions on historical loans, and can pilots be chosen in advance? |
| [Bondora pilot](lender-pilot.md) · [Profiles](pilot-profiles.md) · [Signal sensitivity](pilot-signal-sensitivity.md) · [Field evidence](observed-pilot-evidence.md) | What happened to the Estonian pilots, and did any lender act on such evidence? |
| [Rule](pilot-rule-protocol.md) *protocol* · [Bondora holdout](pilot-holdout.md) · [Prosper](pilot-prosper-protocol.md) *protocol* · [Prosper result](pilot-prosper.md) · [Finnish cases](finnish-pilot-cases.md) | Does a frozen rule recover pilot losses on later loans? |
| [Design](pilot-signal-ml-protocol.md) *protocol* · [Panel](pilot-signal-panel.md) · [Result](pilot-signal-ml.md) | What does one pilot add to the information a lender already receives? |

## 4. Early signals and pooled rates

| Page | Question |
|---|---|
| [Diagnosis](frequency_diagnosis.md) · [Protocol](frequency-protocol.md) *protocol* · [Panel](frequency-panel.md) · [Model](frequency-model.md) · [Test](frequency-test.md) | Why did a historical rate beat boosting, and does an anchored model help? |
| [Dutch history](dutch-frequency.md) · [Weighting rule](local-trust.md) · [Protocol](local-trust-protocol.md) *protocol* · [Wells Fargo test](local-trust-bank.md) | When should a lender trust its own local rate? |
| [Warning condition](early-warning.md) · [Protocol](early-warning-protocol.md) *protocol* · [Dutch cohorts](early-dutch.md) · [Czech test](early-czech.md) | Can early defaults reveal a change in risk before outcomes mature? |
| [Extension results](extension-results.md) | All extension results in one place |

## 5. Process

| Page | Content |
|---|---|
| [Analysis plan](analysis-plan.md) · [Follow-up design](extension-design.md) | Decisions recorded before inspecting results |
| [Data sources](sources.md) | Provenance and file fingerprints |
| [Verification](verification.md) | Tests, independent checks, reproduction and CI |
| [Contributions](contributions.md) | What the authors did, what we added and which standard methods we apply |
