# Lakebase Scale-to-Zero Benchmark Project: Conversation History & Context

**Date created:** May 16, 2026
**Purpose:** Full context handoff for future chat sessions on this project.

---

## Project Goal

Benchmark **Databricks Lakebase Autoscaling** in two configurations to make a defensible production decision:

1. **Instance A:** Always-on (scale-to-zero disabled)
2. **Instance B:** Scale-to-zero enabled (60-second inactivity timeout)

Both instances run identical schema, identical seed data, identical workload via a shared harness. Run duration is **flexible** (user will decide; could be hours or days). Goal is to capture:

- First-query latency after idle periods (cold-resume cost)
- Warm-query latency distribution
- Total compute cost over the run
- Autoscale transition behavior

---

## User Preferences and Tone Requirements

**Critical style rules captured during the conversation:**

1. **Do NOT use em-dashes (—)**. The user explicitly stated this is not their tone.
2. **Do NOT specify run durations** like "24-48 hours" or "Six Months in Production". Keep titles and timeframes generic. User will decide duration later.
3. **Do NOT hallucinate** numbers, results, or outcomes. If results don't exist yet, say so.
4. **Tone reference:** The user's writing style matches this blog (Satya Sure on Medium): *"Azure Databricks Security with Managed Identities: A Credential-Free Architecture"*. Characteristics:
   - Section-led with bold headers (Introduction, Problem Statement, Conclusion)
   - Declarative sentences, technical-but-accessible
   - Light inline code use
   - "Methodology" framing rather than "story" framing
   - No folksy storytelling, no first-person anecdotes
   - Author name attribution at top

---

## Conversation Evolution (What We Built)

### Iteration 1: Original storytelling blog (rejected for style)
First draft was a hands-on production retrospective with fictional logistics SaaS scenario, "Six Months in Production" framing, ~$16K/month cost reductions, etc. User rejected this approach.

### Iteration 2: Benchmark methodology blog (24-48 hr framing, rejected for duration mention)
Reframed as forward-looking benchmark plan with 24-48 hour window. User rejected the duration specification.

### Iteration 3: Final blog (current accepted version)
Generic-duration benchmark methodology blog in Satya Sure tone. **This is the canonical blog version.** See section below.

### Iteration 4: Step-by-step setup instructions
Detailed UI walkthrough for creating both Lakebase Autoscaling projects with verified documentation. **This is the canonical setup guide.** See section below.

---

## CANONICAL BLOG (Final Version)

# Benchmarking Databricks Lakebase: Always-On vs Scale-to-Zero

**Author**: [Your Name]

## Introduction

Databricks Lakebase introduces a serverless Postgres-compatible operational layer that can either run continuously or scale to zero during idle periods. For platform teams evaluating Lakebase for customer-facing workloads, the two configurations carry materially different cost and latency profiles. This blog defines a controlled benchmarking methodology to compare both modes on identical workloads, using a fixed schema, a fixed query set, and platform-emitted billing data.

The methodology described here provisions two Lakebase database instances, runs the same workload against both, and captures first-query latency, warm-query latency, autoscale transitions, and compute cost into a five-table schema. The duration of the comparison is left flexible. The harness will produce comparable measurements whether the run lasts one diurnal cycle or several.

## Problem Statement

Operational Postgres workloads behind customer dashboards, APIs, and webhook integrations typically display bimodal traffic. Business hours generate the majority of query volume, while overnight windows remain near idle. Provisioning continuously for peak utilization introduces three operational concerns:

- Idle compute hours accumulate cost without serving requests.
- Always-on clusters cannot independently demonstrate the latency penalty of cold resume, because the penalty does not exist on that configuration.
- Vendor-published cold-start numbers do not necessarily reflect the behavior observed in a specific region, on a specific workload shape, at a specific point in time.

A direct, side-by-side comparison is required to make a defensible platform decision. The benchmark must isolate the configuration difference (always-on vs scale-to-zero) while holding schema, data, workload, and client behavior constant.

## Benchmark Architecture

Two Lakebase instances are provisioned in the same region. Both share identical configuration except for the idle policy.

| Attribute | Instance A | Instance B |
|---|---|---|
| Idle policy | Always-on | Scale-to-zero |
| Compute size | Identical baseline | Identical baseline |
| Storage | Identical | Identical |
| Schema | Identical | Identical |
| Seed data volume | Identical | Identical |
| Workload source | Shared harness | Shared harness |

A single Python harness, deployed on a separate compute node, issues the same query sequence to both instances at the same wall-clock times. Each query result is written into the latency table along with the `instance_label` identifying the target. This ensures that latency, cost, and autoscale differences are attributable to the configuration, not to workload skew.

## Schema Definition

Five tables capture the dimensions required for the comparison. All five exist on both instances. Two of them (`compute_billing_intervals` and `autoscale_transition_log`) include an `instance_label` column because the benchmark consolidates results into a single analysis layer.

### Table 1: tenant_request_events

Customer traffic log. One row per simulated API request.

```sql
CREATE TABLE tenant_request_events (
    event_id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    tenant_id         UUID NOT NULL,
    request_ts        TIMESTAMPTZ NOT NULL,
    endpoint_path     TEXT NOT NULL,
    http_method       VARCHAR(8) NOT NULL,
    status_code       SMALLINT NOT NULL,
    region_code       VARCHAR(8) NOT NULL,
    bytes_returned    INTEGER,
    user_agent_class  VARCHAR(32)
);

CREATE INDEX idx_tre_tenant_ts ON tenant_request_events (tenant_id, request_ts DESC);
CREATE INDEX idx_tre_endpoint_ts ON tenant_request_events (endpoint_path, request_ts DESC);
```

Sample rows:

| event_id | tenant_id | request_ts | endpoint_path | status_code | user_agent_class |
|---|---|---|---|---|---|
| 1001 | a3f1...c2 | 2026-05-16 06:12:04 | /v2/dispatch/board | 200 | web |
| 1002 | b71e...09 | 2026-05-16 06:12:04 | /v2/drivers/1142/score | 200 | mobile_ios |
| 1003 | a3f1...c2 | 2026-05-16 06:12:05 | /v2/trips/active | 304 | web |

### Table 2: api_session_state

Sessions and API connection metadata.

```sql
CREATE TABLE api_session_state (
    session_id        UUID PRIMARY KEY,
    tenant_id         UUID NOT NULL,
    user_id           UUID NOT NULL,
    started_at        TIMESTAMPTZ NOT NULL,
    last_seen_at      TIMESTAMPTZ NOT NULL,
    ended_at          TIMESTAMPTZ,
    client_kind       VARCHAR(32) NOT NULL,
    request_count     INTEGER NOT NULL DEFAULT 0,
    error_count       INTEGER NOT NULL DEFAULT 0,
    ingress_region    VARCHAR(8) NOT NULL
);

CREATE INDEX idx_ass_tenant_active ON api_session_state (tenant_id, ended_at) WHERE ended_at IS NULL;
CREATE INDEX idx_ass_last_seen ON api_session_state (last_seen_at);
```

Sample rows:

| session_id | tenant_id | started_at | last_seen_at | ended_at | request_count |
|---|---|---|---|---|---|
| 4f2a...11 | a3f1...c2 | 2026-05-16 05:58:11 | 2026-05-16 06:42:03 | NULL | 247 |
| 92cd...77 | b71e...09 | 2026-05-16 06:01:47 | 2026-05-16 06:09:22 | 2026-05-16 06:09:22 | 14 |

### Table 3: compute_billing_intervals

Cost tracking. Populated from platform-emitted billing data after the run.

```sql
CREATE TABLE compute_billing_intervals (
    interval_id       BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    instance_label    VARCHAR(16) NOT NULL,
    interval_start    TIMESTAMPTZ NOT NULL,
    interval_end      TIMESTAMPTZ NOT NULL,
    compute_state     VARCHAR(16) NOT NULL,
    cu_seconds        NUMERIC(12,4) NOT NULL,
    estimated_usd     NUMERIC(10,4) NOT NULL
);

CREATE INDEX idx_cbi_instance_window ON compute_billing_intervals (instance_label, interval_start);
```

Sample rows (values to be populated from billing exports):

| instance_label | interval_start | interval_end | compute_state | cu_seconds |
|---|---|---|---|---|
| always_on | 2026-05-16 02:30:00 | 2026-05-16 02:45:00 | active | (TBD) |
| scale_to_zero | 2026-05-16 02:30:00 | 2026-05-16 02:45:00 | paused | 0.0000 |
| scale_to_zero | 2026-05-16 02:45:12 | 2026-05-16 02:45:13 | resuming | (TBD) |

### Table 4: autoscale_transition_log

State transitions on both instances.

```sql
CREATE TABLE autoscale_transition_log (
    transition_id     BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    instance_label    VARCHAR(16) NOT NULL,
    occurred_at       TIMESTAMPTZ NOT NULL,
    from_state        VARCHAR(16) NOT NULL,
    to_state          VARCHAR(16) NOT NULL,
    trigger_reason    VARCHAR(64) NOT NULL,
    duration_ms       INTEGER,
    notes             TEXT
);

CREATE INDEX idx_atl_instance_time ON autoscale_transition_log (instance_label, occurred_at DESC);
```

For Instance A, this table should remain empty under normal operation. For Instance B, every pause and resume is captured here.

### Table 5: frontend_latency_samples

User-facing latency. One row per harness query, per instance.

```sql
CREATE TABLE frontend_latency_samples (
    sample_id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    instance_label    VARCHAR(16) NOT NULL,
    captured_at       TIMESTAMPTZ NOT NULL,
    query_label       VARCHAR(64) NOT NULL,
    perceived_ms      INTEGER NOT NULL,
    server_ms         INTEGER,
    cold_resume       BOOLEAN NOT NULL DEFAULT FALSE,
    seconds_since_last_query INTEGER,
    error             TEXT
);

CREATE INDEX idx_fls_instance_query_time ON frontend_latency_samples (instance_label, query_label, captured_at);
CREATE INDEX idx_fls_cold ON frontend_latency_samples (cold_resume, captured_at) WHERE cold_resume = TRUE;
```

The `cold_resume` flag is set when the harness has waited long enough that Instance B is expected to be paused. The flag is also recorded for the matching probe on Instance A so the two are directly comparable.

## Benchmark Query Set

Five queries are issued by the harness. They are written to exercise point lookups, range scans, aggregations, and analytical patterns typical of dashboard and API workloads.

**Q1: recent traffic by tenant.** Point lookup, indexed.

```sql
SELECT endpoint_path, http_method, status_code, request_ts
FROM tenant_request_events
WHERE tenant_id = $1
  AND request_ts >= NOW() - INTERVAL '1 hour'
ORDER BY request_ts DESC
LIMIT 100;
```

**Q2: active sessions snapshot.** Filtered aggregation.

```sql
SELECT tenant_id, COUNT(*) AS active_sessions, SUM(request_count) AS total_requests
FROM api_session_state
WHERE ended_at IS NULL
GROUP BY tenant_id
ORDER BY active_sessions DESC
LIMIT 50;
```

**Q3: hourly request volume.** Range scan plus aggregation.

```sql
SELECT
    date_trunc('hour', request_ts) AS hour,
    COUNT(*) AS requests,
    COUNT(DISTINCT tenant_id) AS unique_tenants
FROM tenant_request_events
WHERE request_ts >= NOW() - INTERVAL '6 hours'
GROUP BY 1
ORDER BY 1 DESC;
```

**Q4: latency percentiles by query.** Analytical query on the latency table.

```sql
SELECT
    query_label,
    COUNT(*) AS samples,
    PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY perceived_ms) AS p50,
    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY perceived_ms) AS p95,
    PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY perceived_ms) AS p99
FROM frontend_latency_samples
WHERE captured_at >= NOW() - INTERVAL '1 hour'
GROUP BY query_label;
```

**Q5: autoscale event audit.** Operational query.

```sql
SELECT to_state, trigger_reason, COUNT(*) AS events, AVG(duration_ms) AS avg_ms
FROM autoscale_transition_log
WHERE occurred_at >= NOW() - INTERVAL '24 hours'
GROUP BY to_state, trigger_reason
ORDER BY events DESC;
```

## Workload Schedule

The harness operates on a bimodal schedule. Two burst windows simulate business-hour traffic, separated by quiet and idle periods. The exact times are configured per region. The pattern is structured so that Instance B is given multiple opportunities to enter and exit the paused state.

| Window | Behavior | Purpose |
|---|---|---|
| Burst window 1 | Q1 through Q5 mixed, approximately 5 QPS | Warm steady-state |
| Quiet window | One query every 2 minutes | Light activity, may or may not keep B warm depending on idle threshold |
| Burst window 2 | Same as burst 1 | Second warm cycle |
| Long idle window | No traffic | Allows B to pause; the first query after this window is the cold-resume sample |

At the start of each burst window, the first query against each instance is flagged separately. This single sample, repeated across multiple cycles, is the primary input for the cold-resume comparison.

In addition, probe queries are issued at staggered intervals during the idle window. These probes capture how resume latency varies with idle duration.

## Comparison Queries

The following queries are run on the consolidated analysis layer once the benchmark completes.

**First-query latency after idle.**

```sql
SELECT
    instance_label,
    captured_at,
    query_label,
    perceived_ms,
    seconds_since_last_query
FROM frontend_latency_samples
WHERE cold_resume = TRUE
ORDER BY captured_at, instance_label;
```

**Warm-query latency distribution.**

```sql
SELECT
    instance_label,
    query_label,
    PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY perceived_ms) AS p50,
    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY perceived_ms) AS p95,
    PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY perceived_ms) AS p99,
    COUNT(*) AS samples
FROM frontend_latency_samples
WHERE cold_resume = FALSE
GROUP BY instance_label, query_label
ORDER BY query_label, instance_label;
```

**Total cost across the run.**

```sql
SELECT
    instance_label,
    SUM(estimated_usd) AS total_usd,
    SUM(CASE WHEN compute_state = 'paused'
             THEN EXTRACT(EPOCH FROM (interval_end - interval_start))
             ELSE 0 END) / 3600.0 AS hours_paused,
    SUM(CASE WHEN compute_state = 'active'
             THEN EXTRACT(EPOCH FROM (interval_end - interval_start))
             ELSE 0 END) / 3600.0 AS hours_active
FROM compute_billing_intervals
GROUP BY instance_label;
```

**Autoscale event count on Instance B.**

```sql
SELECT
    trigger_reason,
    COUNT(*) AS transitions,
    AVG(duration_ms) AS avg_duration_ms,
    MAX(duration_ms) AS max_duration_ms
FROM autoscale_transition_log
WHERE instance_label = 'scale_to_zero'
GROUP BY trigger_reason
ORDER BY transitions DESC;
```

## Dashboards and KPIs

Three operational dashboards consume the schema during and after the run.

The **Latency dashboard** plots `perceived_ms` by `instance_label` over time, with cold-resume samples visually separated from warm samples. A secondary panel restricts the view to warm queries only, so that cold spikes do not dominate the y-axis.

The **Cost dashboard** displays running cost totals per instance, alongside a delta panel that shows cumulative savings on the scale-to-zero side. Cost values populate from billing exports as they become available.

The **State dashboard** renders Instance B's compute state as a timeline, overlaid with the corresponding latency samples. This view supports visual correlation between a resume event and the latency observed on the next query.

Primary KPIs reported at the end of the run:

- First-query p50 and p95 latency, Instance A and Instance B
- Warm-query p50, p95, and p99 latency, both instances
- Total compute cost over the run window, both instances
- Ratio of scale-to-zero cost to always-on cost
- Count of paused-to-active transitions on Instance B
- Total hours Instance B spent in the paused state

## Operational Considerations

Several behaviors should be accounted for when interpreting results.

Client-side connection pooling can prevent the scale-to-zero instance from pausing if long-lived connections are held open. The harness deliberately uses short-lived connections so that B is permitted to idle.

The minimum idle timeout supported by the platform determines how aggressively B can scale down. If the configured timeout exceeds the gap between scheduled probe queries, B will not pause during the quiet window, and only the long idle window will produce cold-resume samples.

Billing data may not be available in real time. The cost comparison may need to wait until the billing export catches up after the run completes.

A single run produces a single data point per measurement. The methodology is repeatable, but conclusions about long-term reliability or rare failure modes require longer observation windows than a single benchmark cycle provides.

## Conclusion

The methodology described in this blog isolates the cost and latency impact of Lakebase scale-to-zero against an always-on baseline. By running two identically configured instances under a shared workload harness, and by routing all measurements into a consolidated five-table schema, the benchmark produces directly comparable results across the dimensions that matter for production decisions: first-query latency, warm-query latency, autoscale transition behavior, and compute cost.

The duration of the comparison is configurable. Whether the harness runs for one diurnal cycle or several, the same queries, dashboards, and KPIs apply. The results section will be populated from observed data once the benchmark run is complete.

## References

1. Databricks Lakebase documentation
2. PostgreSQL documentation for `PERCENTILE_CONT` and partitioned tables
3. Internal benchmark harness specification

---

## CANONICAL SETUP INSTRUCTIONS

### Key Lakebase Facts (verified via documentation search, May 2026)

1. **As of March 12, 2026**, all new Lakebase instances are created as **Lakebase Autoscaling projects**. The legacy "Provisioned" path cannot be used for new instances.
2. **Scale-to-zero is disabled by default** on production branches of new Autoscaling projects (to match Provisioned behavior). Must be explicitly enabled.
3. **Minimum scale-to-zero timeout: 60 seconds**. Default: 5 minutes. Maximum: configurable up to 1 hour.
4. **Compute Unit (CU) sizing on Autoscaling:** Each CU = 2 GB RAM (different from Provisioned, which was 16 GB per CU).
5. **Autoscaling range:** 1 to 32 CU maximum.
6. **Workspace limit:** Max 10 instances per workspace.
7. **Connection limit:** Up to 1000 concurrent connections per instance.
8. **Storage limit:** 2 TB logical size across all databases per instance.
9. **Reactivation latency:** Documentation claims "a few hundred milliseconds" but this should be measured, not trusted.
10. **Resources hierarchy:** Workspace > Project > Branch > Compute > Database.

### The two databases to create

| Label | Project name | Scale-to-zero |
|---|---|---|
| Instance A | `bench-always-on` | Disabled |
| Instance B | `bench-scale-to-zero` | Enabled, 60-second timeout |

Both projects use identical compute sizing (min 1 CU, max 4 CU). Only the scale-to-zero setting differs.

### Step-by-step (12 steps)

**Step 1:** Open the Lakebase App from the Apps switcher in the top-right of the Databricks workspace. Stay on the Autoscaling tab.

**Step 2:** Create Instance A. Click Create. Project name: `bench-always-on`. Compute range: min 1 CU, max 4 CU. Accept default Postgres version and region (pick region closest to workload harness).

**Step 3:** Disable scale-to-zero on Instance A. Inside the project > Branches > production > Computes tab > Edit the primary compute > Turn OFF Scale to zero toggle > Save.

**Step 4:** Save Instance A connection string as `INSTANCE_A_CONN`. Format: `postgresql://user@host:5432/databricks_postgres?sslmode=require`

**Step 5:** Create Instance B. Same as Step 2 but name `bench-scale-to-zero`. Same region, same Postgres version, same CU range.

**Step 6:** Enable scale-to-zero on Instance B. Same path as Step 3, but turn ON the toggle. Set inactivity timeout to 60 seconds (minimum). Save. Save connection string as `INSTANCE_B_CONN`.

**Step 7:** Create a service principal for the harness. Settings > Identity and access > Service principals > Add. Name: `lakebase-benchmark-sp`. Generate PAT, save as `SP_TOKEN`. Grant Can Connect permission on both projects.

**Step 8:** Run schema DDL on both instances using the Lakebase SQL Editor. All 5 tables (DDL in blog above). Verify with `SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';`

**Step 9:** Seed identical data into both instances. ~50,000 rows in `tenant_request_events`, ~500 in `api_session_state`. Use `pg_dump --data-only` from one and restore to the other to guarantee identical seed.

**Step 10:** Verify configuration parity. Check compute range, scale-to-zero state, Postgres version, region, table count, row count on both instances.

**Step 11:** Confirm scale-to-zero is actually pausing Instance B. Run `SELECT 1`, wait 90+ seconds, check Computes tab for Suspended status. Run query again and observe cold-resume delay.

**Step 12:** Prepare workload harness with both connection strings, service principal token. Critical: use **short-lived connections** (open, query, close) so Instance B is allowed to idle. Persistent pooled connections will prevent suspension.

### Cost note during setup

Instance A accrues compute cost continuously from creation. Either start the workload immediately after setup, or manually Stop Instance A (Lakebase App > project > Stop) until ready. Instance B only costs storage during idle.

### Post-run data source

Pull billing data from `system.billing.usage` filtered by project IDs to populate `compute_billing_intervals` for the cost comparison.

---

## Outstanding Items / Future Work

1. **Workload harness code:** Not yet written. Needs to be Python, use `psycopg2` or `asyncpg`, short-lived connections, dual-target query issuance, write results to `frontend_latency_samples`.
2. **Seed data generation script:** Not yet written. Needs to produce realistic UUID distribution, time-spread `request_ts` values, and a mix of active/closed sessions.
3. **Dashboard creation:** Three dashboards described in the blog need to be built in Databricks SQL or another BI tool against the harness output tables.
4. **Billing data pull:** Need to confirm whether `system.billing.usage` exposes per-Lakebase-project granularity, or if a different system table is required.
5. **Run execution:** User will decide duration. Could be hours, days, or longer.
6. **Results writeup:** A follow-up blog with actual measured numbers will be written after the run completes.

---

## Important Constraints to Remember in Future Chats

1. **Never use em-dashes (—).** Use periods, commas, parentheses, or "and" instead.
2. **Never specify run duration** unless the user explicitly states one in that conversation.
3. **Never fabricate numbers.** If results don't exist, say so or leave as (TBD).
4. **Match Satya Sure tone:** declarative, technical, methodology-framed, no storytelling, bold section headers, "Author:" attribution at top.
5. **Five tables only:** `tenant_request_events`, `api_session_state`, `compute_billing_intervals`, `autoscale_transition_log`, `frontend_latency_samples`. Do not add a sixth.
6. **Lakebase Autoscaling, not Provisioned.** New instances only come in the Autoscaling flavor.
7. **The user is technical:** senior data engineer / platform engineer audience. Skip basic explanations.

---

## How to Use This File in a Future Chat

Upload this file at the start of a new conversation along with a prompt like:

> "I'm continuing work on a Databricks Lakebase scale-to-zero benchmark project. Attached is the full history file with all context, decisions, the canonical blog, and the setup instructions. Please read it before responding. My next task is: [whatever you need next]."

This will give the new Claude session full context without needing to re-explain anything.
