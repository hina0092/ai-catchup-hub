# AI Catchup Hub

A personal public-RSS reader built with Python and Vue 3.

## Local development

Python 3.11+, Node.js 24 and pnpm 11.25.0.

```sh
python -m unittest discover -s tests -v
python collector/collect.py --overwrite
cd frontend
pnpm install --frozen-lockfile --ignore-scripts
pnpm dev
```

## Deployment

Use a dedicated repository with main as the default branch. Select GitHub Actions in Settings > Pages. After approval, set the repository variable ENABLE_PAGES_DEPLOY to true. Run Test, collect and publish manually. Daily collection is scheduled for 10:17 UTC (19:17 JST); timing is not guaranteed.

Tests, collection and build must succeed before deployment. Total collection failure leaves the deployed site unchanged. Partial source failure publishes the successfully collected sources only. The workflow uploads frontend/dist only and never commits generated data.
