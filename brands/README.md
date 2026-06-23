# brands/ — one subfolder per brand

Each brand the platform manages gets its own folder, fully isolated from every
other brand. Nothing is shared across brands.

```
brands/
├── example.com/            ← committed template (the convention)
│   ├── account.yaml        # audience, canonical_sources, sitemap, cluster_map, gsc mode
│   ├── brand_profile.json  # the SELLING brief (features, value props, ICP, objections, competitors)
│   ├── brand_assets.json   # permission-gated facts for E-E-A-T (author, approved testimonials, screenshots)
│   ├── gsc/                # this brand's GSC export ZIPs/CSVs        (git-ignored)
│   └── runs/               # this brand's audit + content run outputs (git-ignored)
└── <your-brand>/           ← same shape
```

## Managing a brand

```bash
python run.py account add yourbrand.com        # scaffold brands/yourbrand.com/
# edit account.yaml + brand_profile.json + brand_assets.json; drop GSC ZIPs in gsc/
python run.py account list
python run.py account show yourbrand.com
python run.py content --mode rebuild --account yourbrand.com --diagnosis …
```

## What is committed vs private

`example.com/` (this template) is committed so the convention ships with the repo.
**Real brands' `account.yaml` / `brand_profile.json` / `brand_assets.json` are
git-ignored by default** because this repo may be public and brand profiles are
internal strategy. `gsc/` and `runs/` are always ignored.

To version-control a real brand's config (so it persists across machines/sessions):
make the repo private, then remove that brand from the ignore rules in
`.gitignore`. Otherwise keep brand folders local to your machine, or move them to
a secrets store for a multi-tenant deployment.
