# Model card — Player Recruitment Similarity

A card for the model that answers *"who else plays like this player?"*. It is
written for someone deciding whether to trust an answer, not for someone
implementing one — [METHODOLOGY.md](../METHODOLOGY.md) covers the mechanics and
[docs/METRIC_DICTIONARY.md](METRIC_DICTIONARY.md) defines every metric.

| | |
|---|---|
| **Version** | 1.0 |
| **Type** | Unsupervised similarity ranking — weighted cosine over role-standardized features |
| **Owner** | Samuil Radulov |
| **Code** | `src/similarity/feature_matrix.py`, `src/similarity/engine.py` |
| **Configuration** | `artifacts/feature_config.yml` (feature lists, weights, thresholds) |
| **Population** | 344 outfield players, Premier League 2015/16, ≥ 600 minutes |

## What it does

Given a reference player, it returns a ranked list of other players in the same
role group whose **season profile has a similar shape** — who deviate from their
role's average in the same directions and by similar amounts.

Every result is decomposed: the dimensions the two players match on, the
dimensions they differ most on, and the raw values behind both.

## What it does not do

These are not caveats bolted on at the end; they are the boundary of the claim.

- **It does not rank quality.** Two players scoring 0.85 do similar things. One
  may be considerably better than the other. Nothing in the model observes
  outcome quality.
- **It does not assess tactical fit.** A profile match says nothing about whether
  a player would work in a particular system, manager or league.
- **It does not estimate value.** No fee, wage or contract data is used.
- **It does not predict anything.** No match results, no future performance, no
  development curves. The model describes one completed season.
- **It is not a shortlisting tool on its own.** It narrows a search; it does not
  make a decision, and it is not designed to be used without a scout.

## Intended use

**In scope.** Exploratory recruitment research; finding stylistic comparables for
a player already identified; sanity-checking a scout's intuition; teaching or
demonstrating role-aware similarity.

**Out of scope.** Any decision affecting a person — signing, releasing, valuing,
selecting — taken from the model's output alone. Any use presenting the score as
a measure of ability. Any use outside the population below.

## Data

| | |
|---|---|
| **Source** | [StatsBomb Open Data](https://github.com/statsbomb/open-data) |
| **Competition-season** | Premier League 2015/16 |
| **Scale** | 380 matches, 1,313,773 events, 13,678 lineup rows |
| **Unit of analysis** | One player-season |
| **Inclusion** | Outfield players with ≥ 600 minutes and ≥ 70% feature coverage |
| **Exclusions** | Goalkeepers (a different job needing different features); anyone under 600 minutes (per-90 rates on a small sample are noise) |

The 600-minute floor is the single largest filter: it removes most of the squad
and keeps the players a recruiter would actually be researching. A second,
softer threshold at 900 minutes marks results as low-minutes rather than
removing them.

### Known data limitations

- **No dates of birth.** StatsBomb Open Data does not publish them, so the age
  filter described in the product plan cannot be built from this source. This is
  a genuine gap for a recruitment tool and is stated wherever the app shows a
  profile.
- **One league, one season.** No cross-competition or cross-season normalisation
  exists, because there is nothing to normalise against.
- **`player_name` arrives SQL-escaped** for ten players (`N''Golo Kanté`). Repaired
  in the staging layer; see the metric dictionary.
- **Team-minutes reconciliation warns on ~15 of 760 team-matches**, from genuine
  source quirks (temporary absences, red cards, contradictory lineups). Recorded,
  not silently corrected.

## Features

Each of the five role groups (CB, FB, CM, AM_W, ST) has its own feature list and
its own weights, held in `artifacts/feature_config.yml` rather than in code — the
analytical choices are the reviewable artefact, not an implementation detail.

Roles carry 15–23 features each, spanning passing volume and accuracy,
progression, creation, shooting, defensive volume and height, duels, and where on
the pitch the player operates.

Three choices shape what the model can see:

- **Everything is within role.** Standardization, percentiles and candidate
  filtering all happen inside the role group. 40 passes per 90 means one thing
  for a centre-back and another for a winger.
- **Defensive volume is possession-adjusted.** `metric × 0.5 / (1 − possession share)`,
  so a midfielder in a low-possession side is not flattered by having more
  defending to do.
- **Zone features combine left and right.** A left-sided and a right-sided player
  in the same role should read as similar, so the features are mirror-invariant.

**Deliberately excluded: finishing.** Non-penalty goals minus xG is displayed for
context but never enters the similarity. One season of finishing is variance, and
a similarity model that rewarded it would rank players by luck.

## How the score is computed

Features are winsorized at the 1st/99th percentile within role, z-scored, and
missing values imputed to the role mean (z = 0) while per-player coverage is
recorded. Similarity is then weighted cosine on those vectors, which is plain
cosine on √w-scaled ones.

Two properties are worth stating because they are what make the output
defensible:

- **Filtering precedes scoring.** Role, minutes and coverage filters are applied
  before any similarity is computed, so an incompatible player cannot surface on
  a coincidental statistical shape.
- **Every result is explainable.** The weighted per-feature distance decomposes
  into where the players match and where they clash, with raw values shown. A
  result can always be traced back to football.

## Evaluation

There is no ground truth for "similar player", so the model is evaluated on
**stability** — does the answer survive perturbations that should not change it —
and on **face validity**. Reproduce with `scripts/validate_similarity.py`.

| Check | Result | What it establishes |
|---|---|---|
| Keep a random 80% of matches, 5 seeds | **81.2%** of top-10 retained (sd 0.7%) | Rankings reflect season-long style, not a handful of matches |
| Raise the minutes threshold to 900 / 1200 | **98.0% / 98.4%** retained | The answers are not an artefact of the 600-minute cut-off |
| Role weights vs equal weights | **91.7%** retained | The weights refine; the feature *lists* do the work |

**How overlap is measured.** Only baseline recommendations that could still be
returned are counted. Resampling and higher thresholds push some players out of
the qualifying pool entirely, and scoring those as "lost" would measure pool
shrinkage rather than re-ranking. An earlier version of this check did exactly
that and understated stability — most severely at the 1200-minute threshold,
where the raw 76% was almost entirely pool shrinkage.

**Face validity.** Kanté → Gueye (0.80), Cork, Dembélé. Özil → De Bruyne (0.85),
Silva, Payet. Non-penalty xG leaders are Agüero, Vardy and Kane; xA leaders are
De Bruyne and Özil; aerial leaders are Kompany among centre-backs and Carroll
among strikers.

**The weight result deserves emphasis.** Hand-tuned role weights change roughly
one recommendation in twelve. They are a refinement, not the engine. Anyone
reviewing this model should scrutinise the role feature lists first and the
weights second.

## Where it fails

- **Team context is not removed.** A player in a dominant possession side looks
  different from the same player in a counter-attacking side. Possession
  adjustment addresses this for defensive volume only; nothing corrects it for
  passing volume, territory or touch location. **This is the model's biggest
  systematic bias:** two similar players at stylistically opposite clubs will
  score lower than they should, and two ordinary players at similar clubs higher.
- **Role misassignment propagates.** A player is assigned the role they played
  most minutes in. A genuine hybrid — a full-back who spent half a season in
  midfield — is compared against one group and reads oddly in it.
- **Sparse profiles are imputed to average.** A player missing 25% of their
  features has those features silently set to the role mean, which makes them
  look more average than they are. Coverage is shown on every result so this is
  visible; below 70% the player is excluded.
- **Rates on small samples are null, not wrong.** Below their minimum-attempt
  guard, rates are omitted. This is correct but interacts with the point above:
  a low-volume player has more imputed features.
- **Cosine ignores magnitude.** Two players with the same shape but very
  different volume score as similar. This is intended — it is a style model — but
  it surprises people expecting output to matter.
- **One season is one season.** Nothing here distinguishes a player's stable
  style from a single unusual campaign.

## Fairness and ethical considerations

The subjects are professional footballers and the outputs concern their
on-pitch actions in publicly recorded matches. No personal data beyond name,
club and position is processed; no demographic attribute is used or inferred.

The realistic harm is **misuse of the score as a quality judgement** — a player
being passed over because a number next to a better-known name looked low. The
mitigations are that every result carries its explanation and coverage, the
descriptive framing appears on every page that shows a score, and the app states
plainly that similarity is not quality.

Because the model has no ground truth, it cannot be audited for accuracy in the
usual sense. Treat its output as a structured opinion about style, not a
measurement.

## Maintenance

- **Retraining is a rebuild, not a fit.** There are no learned parameters; the
  "model" is the feature configuration plus a distance function. Changing the
  dataset means re-running the pipeline (`scripts/build_staging.py` →
  `build_player_features.py` → `build_app_db.py`).
- **Changing features or weights** means editing `artifacts/feature_config.yml`
  and re-running `scripts/validate_similarity.py`. If stability drops materially
  below the figures above, the change is suspect.
- **168 tests** cover the transformations, features and engine; CI runs them plus
  Ruff on every push.

## Licence and attribution

Data provided by **StatsBomb** under their Open Data user agreement; raw data is
not redistributed by this project. Code is MIT-licensed. See
[DATA_SOURCES.md](../DATA_SOURCES.md).
