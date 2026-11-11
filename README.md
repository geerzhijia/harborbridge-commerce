# HarborBridge Commerce — portable agent company starter
Working name only; no availability checks or business registration have been performed. A human-owned China-to-Amazon commerce operation with a CEO and six specialist roles. This is a runnable local workflow and prompt library, not connected autonomous workers. No model, social platform, supplier, carrier or Amazon account is connected.

Requires Python 3.10+ and Git; no third-party packages.

```sh
python3 tools/company.py init
python3 tools/company.py status
python3 tools/company.py task market "Validate three low-complexity product niches"
# Owner only; substitute the returned task ID:
python3 tools/company.py approve TASK_ID --by owner
python3 tools/company.py context market
python3 tools/company.py checkpoint market "Resume with approved task; next: collect dated sources"
python3 tools/company.py estimate examples/unit-economics.json
python3 tools/company.py export /tmp/harborbridge-migration.zip
python3 -m unittest discover -s tests
```

Use the context output as the starting prompt in any model or platform, perform only approved scope, save reports, then checkpoint. Run `complete TASK_ID --report reports/your-report.md` after saving a report. Completion is recorded as awaiting owner review; owner uses `review TASK_ID --by owner` to accept the report, which does not authorize its recommendations. CLI approval records are local attestations, not identity verification.

Read docs/operating-playbook.md for the workflow, docs/migration.md to move platforms, docs/company-names.md for names, and docs/onboarding.md for missing business facts. The calculator uses illustrative inputs, not live fees, supplier quotes or tax advice. Source and verify actual inputs before an approval decision. No automatic monitoring or scheduling is enabled.

Do not store passwords, identity documents, bank information or raw customer data here. Put secrets in the destination platform's secret manager. Operational records are retained in state/ and reports/; keep private backups and a lawful retention/deletion policy. Git history is not a substitute for a backup.
