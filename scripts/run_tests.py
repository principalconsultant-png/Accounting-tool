"""Run real regression tests and expose failures in the GitHub job summary."""
from pathlib import Path
import os
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8')
result=unittest.TextTestRunner(stream=sys.stdout,verbosity=2).run(unittest.defaultTestLoader.discover(str(ROOT/'tests')))
summary=os.environ.get('GITHUB_STEP_SUMMARY')
if summary:
    lines=['# Regression test result','',f'Ran {result.testsRun}; failures {len(result.failures)}; errors {len(result.errors)}; skipped {len(result.skipped)}.','']
    for test,trace in result.errors+result.failures:
        lines.extend(['## '+str(test),'','```text',trace.replace('```','~~~'),'```',''])
    Path(summary).write_text('\n'.join(lines),encoding='utf-8')
raise SystemExit(0 if result.wasSuccessful() else 1)
