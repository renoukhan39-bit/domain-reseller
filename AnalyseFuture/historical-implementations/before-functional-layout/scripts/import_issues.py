#!/usr/bin/env python3
"""Preview or import the 66 task records as GitHub issues (gh CLI required).

Default is DRY RUN. Only --apply creates issues. Existing issue titles are skipped.
Do not pass personal access tokens as CLI args or hardcode secrets here.
"""
import argparse
import csv
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKLOG = ROOT / 'docs' / 'ISSUE_BACKLOG.csv'


def gh(*args):
    return subprocess.check_output(['gh', *args], text=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--repo', default='renoukhan39-bit/domain-reseller')
    parser.add_argument('--apply', action='store_true', help='create issues in GitHub; default preview')
    args = parser.parse_args()
    with BACKLOG.open(encoding='utf-8', newline='') as f:
        rows = list(csv.DictReader(f))
    if len(rows) != 66:
        raise RuntimeError('Expected 66 task rows; inspect docs/ISSUE_BACKLOG.csv')
    if args.apply:
        existing = {i['title'] for i in json.loads(gh('issue','list','--repo',args.repo,
                        '--state','all','--limit','500','--json','title'))}
    else:
        existing = set()
    for task in rows:
        title = f"[{task['id']}] {task['title']}"
        body = (f"**Task:** {task['id']}\n**Owner group:** {task['team']}\n"
                f"**Priority:** {task['priority']}\n**Initial status:** {task['status']}\n\n"
                f"**Acceptance:** {task['acceptance']}\n\n"
                f"See [`docs/TASKS.md`](https://github.com/{args.repo}/blob/main/docs/TASKS.md).\n\n"
                "- [ ] Implementation verified\n- [ ] Tests added and passing\n"
                "- [ ] Security / money-flow reviewed where relevant\n- [ ] CI passed\n")
        if title in existing:
            print('SKIP existing',title)
        elif args.apply:
            print('CREATE', title)
            gh('issue','create','--repo',args.repo,'--title',title,'--body',body)
        else:
            print('WOULD CREATE',title)
    if not args.apply:
        print(f"DRY RUN: {len(rows)} issues in CSV; use --apply only with owner-approved write access")


if __name__ == '__main__':
    main()
