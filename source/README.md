# Apix backend

Agent SDK, tools, storage, and HTTP service powered by Apixis.

```bash
uv sync --locked
uv run pytest
uv run python -m apix.server
```

Run these commands from this directory so both Apix and Apixis load the supplied
`config.yaml`. See [the integration guide](../docs/apixis-integration.md).
