# Mock complete-run split evidence v1

The content-addressed manifest
`manifests/splits/mock-v1-seeds-000000-000999-v1.json` freezes 1,000 seeds for the `mock-v1`
ruleset and `terminal-victory-v1` objective.

| Property | Result |
|---|---:|
| Train seeds | 800 |
| Validation seeds | 100 |
| Test seeds | 100 |
| Missing seeds | 0 |
| Duplicate assignments | 0 |
| Manifest ID | `sha256:7010c687c42c5ecc47239da7ccd13ebd40d7af9be012b6774be63bb0a160dfe1` |

The checked dataset index has ID
`sha256:a12a8526b0b23746b648b3d782f75c65ff56eefa0c82186ac73cfddb88dffd77`.
It contains three terminal runs, one per partition, and six decision records. The audit assigns two
records to each partition and reports no errors.

Contract tests validate all three JSON schemas. Behavioral tests independently regenerate the split,
reject a seed moved between partitions, reject record-level split fields, reject non-terminal runs
and missing adjacent decisions, and verify that the immutable writers refuse changed content.
