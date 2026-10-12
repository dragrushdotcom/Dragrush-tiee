# Corrected Gateway matched regression

Use the existing scaling potato Codespace and the isolated development worktree. Preserve the original robotics worktree and all prior evidence. Never rerun freeze over published results. Reproduction must use an isolated results directory/worktree and private test credentials as described in REPRODUCE_V4_7.md. Do not expose ports or deploy.

Base source: a7abc0ecc330af583c5a85ccee13c6d59d104a28. The only runtime change from the original 27-run pilot is the measured Gateway backlog correction from 5 to 128. Model, workloads, durability and worker resources are unchanged. The 27 jobs reuse prior workload seeds and randomized order; this is diagnostic regression, not independent held-out confirmation. Fresh databases isolate every run.

From tiee-core-v4.4, provision the same private .env.v47 and local image tags using REPRODUCE_V4_7.md. Start only private tiee47pilot services without published ports. The runner uses two workers, pool size 8, Redis AOF appendfsync always, PostgreSQL durable commits and the same 2-core Codespace.

Commands (published results must first be preserved elsewhere in the isolated reproduction checkout):

    python validation/v47_corrected.py freeze
    python -u validation/v47_corrected.py collect
    python validation/v47_admission_profiles_corrected.py
    python validation/v47_analyze_corrected.py
    /workspaces/tiee-v46-report-venv/bin/python validation/v47_charts_corrected.py

Collection is bounded to 1800 seconds. Every offered event is retained, including refusals, transport errors, expiry and useful-work loss. Source hashes are checked before every run. No workload-based model tuning is permitted. Admission profiles come from the first committed SQL decision-history record, read after measurement. Terminal observations come from committed database state, never HTTP acknowledgment fallback. SQL terminal markers occur before transaction commit; polling is an observation upper bound.

Analyze exact one-sided 95% binomial bounds under synthetic IID validity and 20,000 stratified paired bootstrap draws with Bonferroni 97.5% intervals for the two A3 contrasts. Three trace blocks per condition cannot certify production clustered risk or powered superiority.

After measurement, stop private services while retaining volumes. No production services are changed. Full physical-power, host-loss, disk-corruption and independent powered superiority tests remain outside this round.
