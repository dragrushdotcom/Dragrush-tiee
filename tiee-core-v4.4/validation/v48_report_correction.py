from pathlib import Path
p=Path('V4_8_ENGINEERING_REPORT.md')
s=p.read_text()
heading='## Post-collection analyzer correction'
if heading not in s:
    anchor='## Reproduction and preservation'
    assert anchor in s
    section='''## Post-collection analyzer correction

The preregistered validation/v48_analyze.py was frozen before collection, but its first post-collection run raised a TypeError when it summed the list-valued poll_errors field as a scalar. The failed traceback is retained at results/v48/analysis-driver.log. The raw poll error list is empty in all 36 measured runs.

The corrected results were generated with validation/v48_analyze_postcollection.py. Its sole difference from the frozen analyzer is counting poll error entries with len before summing. Raw observations, pairs, endpoints, bootstrap procedure, interval levels, adoption thresholds, and benchmark inputs did not change. The successful output is results/v48/analysis-driver-postcollection.log. Both analyzer hashes and the source diff are documented in validation/ANALYZER_CORRECTION.md.

'''
    s=s.replace(anchor,section+anchor,1)
p.write_text(s)
print('REPORT_CORRECTION_INSERTED',heading in p.read_text())
