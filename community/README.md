# Community

Each use case owns one subfolder here. Blueprints live under
`community/<usecase>/blueprints/` as one `kind: Blueprint` file per version:

```
community/
└── rag-chatbot/
    └── blueprints/
        ├── rag-chatbot-1.0.0.yaml
        └── rag-chatbot-1.1.0.yaml
```

- A `blueprint-name` may only live in **one** use case folder (CI enforces this).
- Multiple versions of the same blueprint are fine — one file each.
- Every PR is reviewed and merged by SUSE maintainers.

See the top-level [`example/`](../example/) for a working template and
[`CONTRIBUTING.md`](../CONTRIBUTING.md) for the full flow.
