# Cluster card — Team Playing-Style Classification

A card for the model that answers *"which teams played alike?"*. Written for
someone deciding whether to trust a label, not for someone implementing one —
[METHODOLOGY.md](../METHODOLOGY.md) covers the mechanics and
[docs/METRIC_DICTIONARY.md](METRIC_DICTIONARY.md) defines every feature.

| | |
|---|---|
| **Version** | 1.0 |
| **Type** | Unsupervised clustering — PCA then KMeans over league-standardized season style means |
| **Owner** | Samuil Radulov |
| **Code** | `src/features/team_match.py`, `src/features/team_season.py`, `src/clustering/style_model.py` |
| **Configuration** | `artifacts/feature_config.yml` (k, seeds, variance target, labels) |
| **Population** | All 20 Premier League clubs, 2015/16, 38 matches each |

## What it does

Builds 28 style features per team per match, aggregates them to a season profile,
reduces the profile with PCA, and partitions the twenty clubs into three style
groups. It also reports, for each club, its distance to its own cluster centroid
and its nearest neighbours across the whole league.

## What it does not do

- **It does not rank teams.** A cluster describes how a side played, not how
  well. The label carries no quality claim.
- **It does not predict results.** No fixture, no scoreline, no table position.
- **It does not identify a manager's intent.** It observes what happened on the
  pitch, which is the product of intent, personnel, opponents and scorelines.
- **It does not generalise beyond this league-season.** Three clusters fitted to
  twenty teams describe those twenty teams.

## Data and features

| | |
|---|---|
| **Source** | [StatsBomb Open Data](https://github.com/statsbomb/open-data), Premier League 2015/16 |
| **Rows** | 760 team-matches → 20 team-seasons |
| **Features** | 28, across eight dimensions |

The eight dimensions: possession and circulation, progression and directness,
territory, width and crossing, pressing and defensive height, transitions, chance
profile, and risk and ball security.

Two implementation points matter for interpreting the output:

- **Opponent-relative metrics.** Possession share, field tilt and PPDA only mean
  anything with both teams in view, so raw counts are computed per team and then
  joined to the opponent's row in the same match. Possession share and field tilt
  are validated to sum to exactly 1.0 across the two sides of every match.
- **The coordinate flip.** StatsBomb records every event from the acting team's
  perspective, always attacking toward x = 120. Relating one side's pressing to
  the other's passing requires mirroring the pitch: PPDA pairs our defensive
  actions at `x ≥ 48` with their passes at `x ≤ 72`.

**Season aggregation keeps the standard deviation as well as the mean.** A rigid
side and an adaptable one can share a season average; the spread is what
separates them. The standard deviations are reported on the club page but are
**not** clustered on — 28 means plus 28 standard deviations over 20 observations
is far more dimensions than the sample supports.

## How k was chosen

Candidates were scored on silhouette **and** on stability — the mean adjusted
Rand index between the partitions found by 25 random restarts. With twenty
points, stability is the more trustworthy measure, because a silhouette on so few
observations moves sharply for small changes.

| k | Silhouette | Stability (ARI) | Smallest cluster |
|---|---|---|---|
| **3** | **0.276** | **1.000** | 6 |
| 4 | 0.241 | 0.743 | 3 |
| 5 | 0.215 | 0.658 | 2 |
| 6 | 0.184 | 0.564 | 2 |

k = 3 wins on both measures and is also the smallest candidate, so no trade-off
arises. Every restart finds the identical partition. Dropping a random 20% of the
features and refitting reproduces it at ARI 0.87.

**The axes.** Five components explain 84.2% of the variance. PC1 (38.6%) is
control versus directness; PC2 (19.9%) is advanced territory versus a deep,
long-range game. Neither was chosen in advance — they are what the data produced.

## The clusters

**Labels were written only after inspecting the centroids.** Each is recorded in
`artifacts/feature_config.yml` next to the z-scores that justify it.

| Cluster | Teams | Defining evidence (centroid z-scores) |
|---|---|---|
| **Possession-dominant high press** | Arsenal, Chelsea, Liverpool, Man City, Man Utd, Spurs | field tilt +1.33, possession +1.27, passes per possession +1.22, defensive height +1.08; PPDA −1.18 (low = aggressive), long passes −1.14 |
| **Direct and wide** | Palace, Leicester, Norwich, Southampton, Sunderland, Watford, West Brom, West Ham | forward distance per pass +0.94, cross share +0.93, long passes +0.90, turnovers +0.96; possession −0.91, pass completion −1.04 |
| **Deep build-up, low territory** | Bournemouth, Villa, Everton, Newcastle, Stoke, Swansea | own-half losses +0.77, backward passes +0.71, PPDA +0.39 (high = passive); attacking-third touches −1.16, high regains −1.16, mean action x −1.02 |

**The middle cluster is deliberately not called "counter-attacking".**
`counter_shot_share` is not among its defining features, so the evidence does not
support that name however natural it sounds for those teams. Naming a cluster
after a trait it does not actually show is the most common way this kind of model
misleads.

### Face validity

The features recover the season without being told anything about it: Man Utd and
Arsenal top for possession; West Brom, Leicester and Sunderland most direct; Spurs
(PPDA 1.92) and Liverpool (1.93) the most aggressive pressers; league-mean
set-piece shot share 25.5%, matching published benchmarks. Leicester's title
season comes out 100th percentile for shots and final-third entries per 100
passes and 5th–15th for possession and pass completion.

## Where it fails

- **Style and quality are entangled.** The possession cluster is exactly the "big
  six", and possession share and field tilt correlate with team strength — so
  that cluster partly reflects quality, not only tactics. **This is the sharpest
  criticism of the model and it should be stated before anyone else spots it.**
  The counter-evidence is the direct cluster, which contains the champions
  (Leicester) alongside two relegated sides (Norwich, Sunderland) — teams at
  opposite ends of the table sharing one style. So the clusters are not merely a
  league table in disguise; but on the possession axis the two effects cannot be
  separated with one season of one league.
- **Twenty observations is a very small sample.** PCA on 28 features over 20
  points is unstable in principle. What justifies trusting *this* solution is the
  stability evidence — perfect ARI across restarts, 0.87 across feature subsets —
  not the sample size, which is bad.
- **A label is a summary, not a boundary.** Nearest-team similarity is computed by
  Euclidean distance in the full standardized space, not the PCA projection, and
  neighbours cross cluster lines freely: Liverpool's nearest sides include
  Everton, from a different cluster. A team sitting between two styles should not
  be trapped by its label, and the app is built so it is not.
- **Outliers exist and are surfaced, not hidden.** Distance to a team's own
  centroid is stored and displayed. Arsenal (4.89) is the least typical member of
  the possession cluster and Leicester (4.78) of the direct cluster — both
  genuinely unusual sides that season, and the label describes them least well.
- **Season means hide in-season change.** A side that changed manager or shape in
  January is represented by one averaged profile. The match-to-match standard
  deviations hint at this but do not decompose it.
- **Opponent quality is not controlled.** A team's style partly reflects who it
  played and what the scoreline was. Over 38 matches the schedule roughly
  balances, but game-state effects do not.

## Intended use

**In scope.** Describing how a league's teams played; finding stylistically
comparable sides; contextualising a player's output by their team's style;
teaching unsupervised methods on a small, interpretable dataset.

**Out of scope.** Any claim about team quality, any forecast, and any transfer of
these three labels to another league or season without refitting.

## Maintenance

- **Refitting is a pipeline run**, not a training job: `scripts/build_staging.py`
  → `build_team_features.py` → `build_team_clusters.py` → `build_app_db.py`.
- **`scripts/build_team_clusters.py --explore`** prints the k evaluation table and
  the centroids. Run it *before* fitting, and rewrite the labels from the new
  centroids — a label carried over from a previous fit is a label with no
  evidence behind it.
- If stability drops materially below ARI 1.00 across restarts, k is no longer
  supported by the data and should be re-chosen.

## Licence and attribution

Data provided by **StatsBomb** under their Open Data user agreement; raw data is
not redistributed by this project. Code is MIT-licensed. See
[DATA_SOURCES.md](../DATA_SOURCES.md).
