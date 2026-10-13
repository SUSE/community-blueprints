# Community

Each contributor owns one subfolder here, named after their GitHub handle or
project. Blueprints live under `community/<contributor>/blueprints/` as one
`kind: Blueprint` file per version:

```
community/
└── acme/
    └── blueprints/
        ├── acme-rag-1.0.0.yaml
        └── acme-rag-1.1.0.yaml
```

- A `blueprint-name` may only be owned by **one** contributor folder (CI enforces this).
- Multiple versions of the same blueprint are fine — one file each.
- Every PR is reviewed and merged by SUSE maintainers, but the blueprints are
  **not supported by SUSE**. The contributor named in the
  `ai-factory.suse.com/maintainer` annotation maintains them.

See the top-level [`example/`](../example/) for a working template and
[`CONTRIBUTING.md`](../CONTRIBUTING.md) for the full flow.
