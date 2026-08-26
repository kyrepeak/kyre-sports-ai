# WNBA Step 5V — immutable publication + staging handoff

Step 5V bridges the tested Docker candidate to a real registry-pinned Render staging deployment without activating sportsbook/model work.

## Safety boundary

Keep `WNBA_PRODUCTION_RUNTIME_ENABLED=false` for the entire Step 5V handoff. Step 5V does not call the sportsbook provider, does not run Monte Carlo, does not call the manual refresh endpoint, and does not provision Render resources.

## Publish the image

Use the manual GitHub Actions workflow:

```text
.github/workflows/wnba-publish-staging-image.yml
```

It is `workflow_dispatch` only. It publishes the selected Git revision to GHCR with immutable release/revision tags and records the final registry digest. It never creates a `:latest` tag.

The deployment value must use this exact form:

```text
ghcr.io/kyrepeak/kyre-sports-api@sha256:<64-hex-registry-digest>
```

Set the exact same value in both:

```text
WNBA_DEPLOYMENT_IMAGE_REF
WNBA_RELEASE_PUBLISHED_IMAGE_REF
```

Then set:

```text
WNBA_RELEASE_REGISTRY=ghcr.io
WNBA_RELEASE_IMAGE_REPOSITORY=ghcr.io/kyrepeak/kyre-sports-api
WNBA_RELEASE_PUBLICATION_VERIFIED=true
WNBA_RELEASE_PUBLISHER=github-actions
WNBA_RELEASE_SOURCE_REPOSITORY=kyrepeak/kyre-sports-ai
WNBA_RELEASE_HANDOFF_FORMAT=render-staging-v1
```

## Verify the handoff

The registered runtime routes are:

```text
GET /api/v1/wnba/runtime/handoff
GET /api/v1/wnba/runtime/handoff-plan
```

`/handoff` is green only when the frozen Step 5U host contract is green, the runtime is still disabled, the GHCR digest is immutable, the published image exactly matches Step 5T, source/host repository identity agrees, and host/storage identities are present.

## Generate the sanitized bundle

Run:

```bash
python -m sports_api.tools.wnba_release_handoff .wnba-step5v-handoff
```

The bundle contains a manifest, ordered handoff plan, a sanitized Render environment handoff, and SHA-256 checksums. Real sportsbook/HMAC secrets are never written into the bundle.

## Render handoff

Use:

```text
sports_api/hosting/render.staging.yaml.template
```

Replace `__IMMUTABLE_IMAGE_REF__` with the exact GHCR `name@sha256` value from the publication workflow. Keep exactly one Render service instance, attach the persistent disk at `/var/lib/kyre-sports-api`, supply secrets only in Render's secret manager, and leave runtime activation off.

Step 5W is the first step allowed to evaluate explicit sportsbook/model activation after the real host, image, release, and persistent-storage identities have all been reverified.
