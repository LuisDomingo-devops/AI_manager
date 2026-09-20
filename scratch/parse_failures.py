import sys
import re

with open('test_results.log', 'r', encoding='utf-8', errors='replace') as f:
    content = f.read()

# Extract only the FAILURE blocks
# Pytest failure blocks look like:
# _ _ _ _ _ _
# ...
# E       AssertionError: ...

failures = re.split(r'={5,} FAILURES ={5,}', content)
if len(failures) > 1:
    summary = failures[1].split('={5,} short test summary info ={5,}')[0]
    with open('scratch/failures_summary.txt', 'w', encoding='utf-8') as out:
        out.write(summary[:45000])  # limit to not exceed view limits
else:
    print("Could not find failures block")
