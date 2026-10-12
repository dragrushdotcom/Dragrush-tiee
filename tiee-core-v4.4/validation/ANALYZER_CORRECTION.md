# v4.8 post-collection analyzer correction

The benchmark plan froze validation/v48_analyze.py before collection (SHA256 1ea9458391e94d3324020f507c38420f4959686d0ec2f4295153c9e5a222b146). After all 36 runs were collected, the first analysis raised TypeError because poll_errors is a list of polling error records, not a numeric scalar. The raw field was confirmed as an empty list in all 36 runs. The first failed analysis log is retained at results/v48/analysis-driver.log.

The analysis was rerun with validation/v48_analyze_postcollection.py (SHA256 48396d33c48fec3a5262b6888c457f4813b8a5bb7753048340b1730a6951c3e1). Its sole code difference from the frozen file is replacing sum(r['poll_errors'] for r in selected) with sum(len(r['poll_errors']) for r in selected). This counts recorded error events. It does not modify source/runtime artifacts, raw observations, sample pairing, endpoints, bootstrap resampling, interval levels, or adoption thresholds. The corrected output is results/v48/analysis-driver-postcollection.log and results/v48/analysis.json.

The failed frozen analyzer and its planned hash remain preserved. Reproduction instructions use the corrected post-collection analyzer.
