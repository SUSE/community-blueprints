# SUSE AI Factory — Community Blueprints

A single catalog repository hosting **community-contributed blueprints** for
[SUSE AI Factory](https://github.com/SUSE/aif). Each contributor curates their
own folder; SUSE AI Factory syncs the whole repo into a cluster via Fleet.

> [!WARNING]
> Community blueprints are **not supported by SUSE**. They are provided as-is,
> maintained by their contributors, and come with no SUSE support, SLA or
> security guarantee. Review each blueprint before installing it. For
> supported content use the SUSE blueprints shipped with SUSE AI Factory, or
> [partner blueprints](https://github.com/SUSE/partner-blueprints).

A **Blueprint** is a `kind: Blueprint` custom resource
(`ai-factory.suse.com/v1alpha1`) describing an AI workload as a set of Helm
components and their values. This repo also publishes an aggregate
[`community/catalog.yaml`](community/catalog.yaml) — a `BlueprintCatalog` CR
listing every community blueprint. Its blueprints list is **generated** by
`scripts/catalog.py gen`, not hand-edited: contributors regenerate it and
commit it with their blueprint, and CI fails the PR if it's stale.

## Repository layout

```
community-blueprints/
├── community/                # one folder per contributor
│   ├── catalog.yaml          # aggregate BlueprintCatalog CR (run `catalog.py gen`; CI checks it)
│   └── <contributor>/
│       ├── blueprints/<name>-<version>.yaml
│       └── clusterrepos/<name>.yaml   # optional, maintainer-approved (see below)
├── example/                  # a working template (validated, not published)
├── scripts/                  # validation + catalog generation
└── .github/workflows/        # the PR validation gate
```

## How SUSE AI Factory consumes this repo

The operator adds an external catalog at runtime through its Helm values —
one entry becomes one Fleet `GitRepo` that applies the CRs in this repo:

```yaml
# aif-operator values.yaml
blueprintCatalogs:
  - name: community-blueprints
    repoURL: https://github.com/SUSE/community-blueprints.git
    branch: main
    paths: [community]
```

Fleet applies **every manifest** under `community/**`: the `Blueprint` files, any
`ClusterRepo` files and the aggregate `BlueprintCatalog`. It garbage-collects
anything removed from the repo.
CI therefore rejects every other manifest under `community/`: only
`blueprints/*.yaml`, `clusterrepos/*.yaml` and `catalog.yaml` are accepted
(no `fleet.yaml`, `kustomization.yaml`, RBAC, `.yml`/`.json` files or symlinks).

A `ClusterRepo` (`catalog.cattle.io/v1`) registers a Helm chart source for
Blueprints. It has a fixed shape (name and `https` URL only) and must match an
entry in `ALLOWED_CLUSTERREPOS` in `scripts/catalog.py`, so adding one needs a
maintainer-reviewed change. Because Fleet removes a `ClusterRepo` from clusters
when its file is deleted, never remove one while Blueprints still use it.
Nothing is added to a cluster unless an administrator opts in with this entry.

Community blueprints use `spec.source: Custom` and may set an optional
`spec.icon`. The Blueprint CRD has no `Community` source yet; a dedicated one
is planned, and this repo will switch to it once SUSE AI Factory supports it.
`spec.icon` needs an aif-operator whose Blueprint CRD includes it (newer than
2.2.0).

## Contributing a blueprint

1. Read [CONTRIBUTING.md](CONTRIBUTING.md).
2. Copy [`example/`](example/) to `community/<your-handle>/`.
3. Open a pull request. CI validates schema + conventions; a SUSE maintainer
   reviews before merge. You remain the maintainer of your blueprint.

## Validation locally

```bash
pip install --require-hashes -r requirements.txt
python scripts/catalog.py validate     # schema/convention checks
python scripts/catalog.py gen          # regenerate community/catalog.yaml
python -m unittest -q scripts/test_catalog.py
```

## License

[Apache License 2.0](LICENSE).
