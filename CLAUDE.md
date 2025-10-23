# CircleCI to GitHub Actions Migration Guide

This repository is being migrated from CircleCI to GitHub Actions. This guide provides the Mozilla-specific patterns and requirements to follow during migration.

---

## Overview

Mozilla is migrating CI pipelines from CircleCI to GitHub Actions. When helping with this migration, you must follow Mozilla's specific patterns for:
- Docker image management via Google Artifact Registry (GAR)
- GCP authentication using OIDC and Workload Identity Federation
- PyPI publishing with Trusted Publishing
- Security requirements for GitHub workflows

---

## Docker Images & Google Artifact Registry (GAR)

### Requirements
- Docker images must be pushed to GAR in the `moz-fx-data-artifacts-prod` project
- Each repository needs explicit permission added to **dataservices-infra**
  - Repository: https://github.com/mozilla/dataservices-infra
  - File: `data-artifacts/tf/prod/locals.tf`
- Use `mozilla-it/deploy-actions/docker-push@v4.3.2` for pushing images
- Authentication uses OIDC with Workload Identity Federation

### Docker Build and Push Pattern

```yaml
jobs:
  build-and-push:
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    permissions:
      contents: read
      id-token: write
    steps:
      - uses: actions/checkout@v4

      - name: Build the Docker image
        run: docker build . -t us-docker.pkg.dev/moz-fx-data-artifacts-prod/<repo_name>/<image_name>:latest

      - name: Push Docker image to GAR
        uses: mozilla-it/deploy-actions/docker-push@v4.3.2
        with:
          project_id: moz-fx-data-artifacts-prod
          image_tags: us-docker.pkg.dev/moz-fx-data-artifacts-prod/<repo_name>/<image_name>:latest
          workload_identity_pool_project_number: ${{ vars.GCPV2_WORKLOAD_IDENTITY_POOL_PROJECT_NUMBER }}
          service_account_name: <repo_name>
```

---

## GCP Authentication

### Standard GCP Access (BigQuery, Cloud Storage, etc.)

```yaml
jobs:
  some_job:
    permissions:
      contents: read
      id-token: write
    environment: GH Actions
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Authenticate to GCP (OIDC)
        uses: google-github-actions/auth@v2
        with:
          workload_identity_provider: ${{ vars.GCPV2_GITHUB_WORKLOAD_IDENTITY_PROVIDER }}
          service_account: ${{ secrets.GCP_SERVICE_ACCOUNT_EMAIL }}
```

### ID Token Generation (Integration Tests, Cloud Functions)

**CRITICAL: When to use this pattern:**
- ANY job that runs integration tests
- Jobs with names containing: `integration`, `integration_test`, `integration-test`
- Config mentions `use_cloud_function`, `dryrun`, or `sql-validation`
- Tests that call Cloud Functions (bigquery-etl-dryrun, etc.)
- Any pytest command with integration test markers

**Infrastructure Requirement:**
Before this will work, you need a cloudops-infra PR to enable the repository and generate a service account:
- Repository: https://github.com/mozilla-services/cloudops-infra
- File: `projects/data-shared/tf/modules/cloudfunctions/main.tf`
- Add repository name to the `github_repositories` list (line 6)
- This creates the dryrun service account and grants Cloud Run function access

```yaml
- name: Authenticate to GCP and Generate ID Token
  id: auth
  uses: google-github-actions/auth@v2
  with:
    workload_identity_provider: ${{ vars.GCPV2_GITHUB_WORKLOAD_IDENTITY_PROVIDER }}
    service_account: ${{ secrets.GCP_DRYRUN_SERVICE_ACCOUNT_EMAIL }}
    token_format: 'id_token'
    id_token_audience: 'https://us-central1-moz-fx-data-shared-prod.cloudfunctions.net/bigquery-etl-dryrun'
    id_token_include_email: true

- name: Export ID Token for Python
  run: echo "GOOGLE_GHA_ID_TOKEN=${{ steps.auth.outputs.id_token }}" >> $GITHUB_ENV
```

**Key requirements (ALL must be present):**
- Use `GCP_DRYRUN_SERVICE_ACCOUNT_EMAIL` secret (NOT `GCP_SERVICE_ACCOUNT_EMAIL`)
- MUST set `token_format: 'id_token'`
- MUST export `GOOGLE_GHA_ID_TOKEN` environment variable
- MUST set `id_token_audience` to the Cloud Function URL
- MUST include `id_token_include_email: true`

---

## Python Setup

### Always Use setup-python Action

**IMPORTANT:** Always use `actions/setup-python` instead of Python Docker containers.

**CRITICAL**: Match the EXACT Python version from CircleCI:
- CircleCI `cimg/python:3.10` → GHA `python-version: '3.10'`
- CircleCI `python:3.11` → GHA `python-version: '3.11'`
- DO NOT change Python versions during migration

```yaml
steps:
  - uses: actions/checkout@v4

  - uses: actions/setup-python@v5
    with:
      python-version: '3.10'  # MUST match CircleCI version EXACTLY
      cache: 'pip'  # Automatically caches pip dependencies
```

**Never use container for Python:**
```yaml
# ❌ WRONG
container:
  image: cimg/python:3.10

# ✅ CORRECT
steps:
  - uses: actions/setup-python@v5
    with:
      python-version: '3.10'
      cache: 'pip'
```

---

## PyPI Trusted Publishing

**Use OIDC instead of API tokens.** Only publish from main branch tags.

### Dedicated Workflow for Tags

```yaml
name: Tagged Deploy

on:
  push:
    branches:
      - main
    tags:
      - '[0-9][0-9][0-9][0-9].[0-9]{1,2}.[0-9]+'  # Calver: YYYY.M.MINOR

jobs:
  deploy:
    # CRITICAL: Verify we're on main branch even with tag trigger
    if: github.ref_name == 'main' || github.event.base_ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    permissions:
      contents: read
      id-token: write
    environment:
      name: pypi
      url: https://pypi.org/p/<package-name>
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.10'

      - name: Install build dependencies
        run: pip install --upgrade build

      - name: Build distribution files
        run: python -m build --sdist

      - name: Publish distribution to PyPI
        uses: pypa/gh-action-pypi-publish@release/v1
```

### CRITICAL: Do NOT Use Twine

**NEVER include twine:**
- ❌ Do NOT install `twine`
- ❌ Do NOT run `twine upload`
- ✅ ONLY use `pypa/gh-action-pypi-publish@release/v1`

---

## Secrets and Variables

### Usage Pattern
- **Sensitive data** → Repository Secrets: `${{ secrets.NAME }}`
- **Non-sensitive config** → Repository Variables: `${{ vars.NAME }}`
- Service account emails must be stored as secrets

### Common Secrets/Variables
- `GCPV2_GITHUB_WORKLOAD_IDENTITY_PROVIDER` (variable)
- `GCPV2_WORKLOAD_IDENTITY_POOL_PROJECT_NUMBER` (variable)
- `GCP_SERVICE_ACCOUNT_EMAIL` (secret)
- `GCP_DRYRUN_SERVICE_ACCOUNT_EMAIL` (secret - for integration tests)
- `GCP_INTEGRATION_SERVICE_ACCOUNT_EMAIL` (secret - for integration tests)

---

## Path Filtering with Reusable Workflows

Use `tj-actions/changed-files` to replace CircleCI's path-filtering orb.

### Define Reusable Workflow

```yaml
# .github/workflows/changed-files.yml
name: Get changed files

on:
  workflow_call:
    inputs:
      path_filter:
        type: string
        required: false
        default: '**'
    outputs:
      any_changed:
        value: ${{ jobs.changed.outputs.any_changed }}
      all_changed_files:
        value: ${{ jobs.changed.outputs.all_changed_files }}

jobs:
  changed:
    runs-on: ubuntu-latest
    outputs:
      any_changed: ${{ steps.changed-files.outputs.any_changed }}
      all_changed_files: ${{ steps.changed-files.outputs.all_changed_files }}
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - uses: tj-actions/changed-files@v44
        id: changed-files
        with:
          files: ${{ inputs.path_filter }}
```

### Call Reusable Workflow

```yaml
jobs:
  changed:
    uses: ./.github/workflows/changed-files.yml
    with:
      path_filter: |
        jetstream/**
        definitions/**

  validate:
    needs: changed
    if: needs.changed.outputs.any_changed == 'true'
    runs-on: ubuntu-latest
    steps:
      - run: echo "Changed files: ${{ needs.changed.outputs.all_changed_files }}"
```

---

## Container Jobs

For jobs requiring specific Docker images:

```yaml
jobs:
  validate:
    runs-on: ubuntu-latest
    container:
      image: gcr.io/moz-fx-data-experiments/jetstream:latest
    permissions:
      contents: read
      id-token: write
    steps:
      - uses: actions/checkout@v4
        with:
          ref: ${{ github.head_ref }}

      - name: Set safe directory
        run: git config --global --add safe.directory "$GITHUB_WORKSPACE"
```

---

## Triggering Airflow DAGs

```yaml
jobs:
  trigger-airflow:
    runs-on: ubuntu-latest
    permissions:
      id-token: write
      contents: read
    steps:
      - name: Authenticate to GCP and Generate ID Token
        id: auth
        uses: google-github-actions/auth@v2
        with:
          workload_identity_provider: ${{ vars.GCPV2_GITHUB_WORKLOAD_IDENTITY_PROVIDER }}
          service_account: ${{ secrets.GCP_SERVICE_ACCOUNT_EMAIL }}
          project_id: ${{ vars.GCLOUD_PROJECT }}
          token_format: id_token
          id_token_audience: https://us-west1-moz-fx-telemetry-airflow-prod.cloudfunctions.net/ci-external-trigger
          id_token_include_email: true
          create_credentials_file: false

      - name: Prepare DAG run note
        run: |
          echo "DAGRUN_NOTE=DAG triggered by **[${{ github.actor }}](https://github.com/${{ github.actor }})** from ${{ github.repository }} CI build [${{ github.run_number }}](${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }})" >> $GITHUB_ENV

      - name: Trigger Airflow DAG
        env:
          ID_TOKEN: ${{ steps.auth.outputs.id_token }}
        run: |
          curl --location --request POST "https://us-west1-moz-fx-telemetry-airflow-prod.cloudfunctions.net/ci-external-trigger" \
            -H "Authorization: bearer $ID_TOKEN" \
            -H "Content-Type: application/json" \
            -d "{\"dagrun_note\": \"${DAGRUN_NOTE}\", \"dag_id\":\"looker\"}"
```

**Key Points:**
- ID token MUST be passed via environment variable (security requirement)
- Repository needs to be added to dataservices-infra for Cloud Run Function permissions

---

## Security Requirements

**Reference**: https://wiki.mozilla.org/GitHub/Repository_Security/GitHub_Workflows_%26_Actions

### Input Validation and Encoding

**CRITICAL**: Never use externally-controlled parameters directly in shell commands.

**Vulnerable parameters:**
- `github.event.issue.title`, `github.event.issue.body`
- `github.event.pull_request.title`, `github.event.pull_request.body`, `github.event.pull_request.head.ref`
- `github.head_ref`, `github.ref_name`
- `github.event.commits.*.message`, `github.event.commits.*.author.name`

**WRONG:**
```yaml
- run: echo "${{ github.event.pull_request.title }}"
- run: git checkout ${{ github.head_ref }}
```

**CORRECT - Use environment variables:**
```yaml
- name: Process PR title
  env:
    PR_TITLE: ${{ github.event.pull_request.title }}
    BRANCH: ${{ github.head_ref }}
  run: |
    echo "$PR_TITLE"
    git checkout "$BRANCH"
```

### Least Privilege Requirements

```yaml
permissions:
  contents: read
  id-token: write  # Only if needed for OIDC
```

### Third-Party Action Pinning

**CRITICAL**: Pin third-party actions to specific commit SHAs.

**Exceptions** - Official GitHub/Mozilla actions can use version tags:
- `actions/checkout@v4`
- `actions/setup-python@v5`
- `google-github-actions/auth@v2`
- `mozilla-it/deploy-actions/*@v4.3.2`

---

## Common Pattern Conversions

| CircleCI | GitHub Actions |
|----------|----------------|
| `setup: true` + `path-filtering` orb | Reusable workflows with `tj-actions/changed-files` |
| `circleci step halt` | `exit 0` or conditional logic |
| `CIRCLE_PR_NUMBER` | `context.issue.number` |
| `CIRCLE_SHA1` | `github.sha` |
| `CIRCLE_BRANCH` | `github.ref_name` |
| `restore_cache` / `save_cache` | `actions/cache@v3` or `cache: 'pip'` |

---

## Critical Rules for Migration

1. **Security - Input Encoding**: Never use `${{ github.event.* }}` or `${{ github.head_ref }}` directly in shell commands
2. **Security - Permissions**: Use minimal permissions, set `permissions: {}` when GITHUB_TOKEN not needed
3. **Python Setup**: Always use `actions/setup-python@v5` with `cache: 'pip'`, never Python containers
4. **Python Version**: MUST match CircleCI Python version exactly (e.g., 3.10 stays 3.10)
5. **PyPI Publishing**: NEVER use `twine`, only `pypa/gh-action-pypi-publish@release/v1`
6. **Tagged Deploys**: Add `if: github.ref_name == 'main' || github.event.base_ref == 'refs/heads/main'` to tag-triggered jobs
7. **ID Token Auth**: For integration tests, use ID token pattern with `GCP_DRYRUN_SERVICE_ACCOUNT_EMAIL`
8. **Complete Commands**: Copy ALL lines from CircleCI `run:` commands to GitHub Actions, including multi-line curl commands

---

## Infrastructure Changes Needed

When migrating, you may need to create PRs in other repositories:

### Docker Builds → dataservices-infra PR
If CircleCI config builds and pushes Docker images, you need to add the repository to GAR access:
- Repository: https://github.com/mozilla/dataservices-infra
- File: `data-artifacts/tf/prod/locals.tf`
- Add repository name to the list

### Airflow DAG Triggers → dataservices-infra PR
If CircleCI config triggers Airflow DAGs, you need a service account:
- Repository: https://github.com/mozilla/dataservices-infra
- File: `telemetry-airflow/tf/prod/main.tf`
- Add repository name to the service account list

### Dryrun/SQL Validation (Integration Tests) → cloudops-infra PR
If CircleCI config uses dryrun, SQL validation, or calls Cloud Functions (bigquery-etl-dryrun), you need to enable the repository:
- Repository: https://github.com/mozilla-services/cloudops-infra
- File: `projects/data-shared/tf/modules/cloudfunctions/main.tf`
- Add repository name to the `github_repositories` list (line 6)
- This creates the `GCP_DRYRUN_SERVICE_ACCOUNT_EMAIL` and grants Cloud Run function access
- Required for: integration tests, pytest with `--sql` flag, bigquery-etl-dryrun calls

---

## Testing Your Migration

1. **Preview workflows** without writing files to verify correctness
2. **Create a feature branch** for the migration
3. **Test workflows on the branch** before merging to main
4. **Verify protected operations** (Docker push, PyPI publish) only run on main
5. **Check secrets** are configured in repository settings
6. **Monitor first runs** for authentication and permission issues

---

## Complete Migration Examples

### Example 1: Simple Docker Build and Push

**Before (CircleCI):**
```yaml
version: 2.1

orbs:
  gcp-gcr: circleci/gcp-gcr@0.16.2

jobs:
  test:
    docker:
      - image: cimg/base:current
    steps:
      - checkout
      - setup_remote_docker
      - run:
          name: Build image
          command: make build
      - run:
          name: Test Code
          command: make test

workflows:
  version: 2
  build:
    jobs:
      - test:
          filters:
            tags:
              only: /.*/
      - gcp-gcr/build-and-push-image:
          context: data-eng-airflow-gcr
          image: firefox-public-data-report-etl
          filters:
            branches:
              only: main
```

**After (GitHub Actions):**
```yaml
name: Build and Deploy

on:
  push:
    branches:
      - main
  pull_request:

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: docker/setup-buildx-action@v3
      - name: Build image
        run: make build
      - name: Test code
        run: make test

  build-and-push-image:
    if: github.ref == 'refs/heads/main'
    needs: test
    runs-on: ubuntu-latest
    permissions:
      contents: read
      id-token: write
    steps:
      - uses: actions/checkout@v4
      - name: Build the Docker image
        run: docker build . -t us-docker.pkg.dev/moz-fx-data-artifacts-prod/firefox-public-data-report-etl/firefox-public-data-report-etl:latest
      - name: Push Docker image to GAR
        uses: mozilla-it/deploy-actions/docker-push@v4.3.2
        with:
          project_id: moz-fx-data-artifacts-prod
          image_tags: us-docker.pkg.dev/moz-fx-data-artifacts-prod/firefox-public-data-report-etl/firefox-public-data-report-etl:latest
          workload_identity_pool_project_number: ${{ vars.GCPV2_WORKLOAD_IDENTITY_POOL_PROJECT_NUMBER }}
          service_account_name: firefox-public-data-report-etl
```

---

### Example 2: Python Package with Tests and PyPI Deploy

**Before (CircleCI):**
```yaml
version: 2.1

jobs:
  build:
    docker:
      - image: python:3.10
    steps:
      - checkout
      - run:
          name: Build
          command: |
            python3.10 -m venv venv/
            venv/bin/pip install -r requirements.txt
      - run:
          name: ruff lint
          command: venv/bin/ruff check jetstream
      - run:
          name: PyTest
          command: venv/bin/pytest --ignore=tests/integration/

  integration:
    docker:
      - image: python:3.10
    steps:
      - checkout
      - run:
          name: Build
          command: |
            python3.10 -m venv venv/
            venv/bin/pip install -r requirements.txt
      - run:
          name: PyTest Integration Test
          command: |
            export GOOGLE_APPLICATION_CREDENTIALS="/tmp/gcp.json"
            echo "$GCLOUD_SERVICE_KEY_INTEGRATION_TEST" > "$GOOGLE_APPLICATION_CREDENTIALS"
            venv/bin/pytest --integration tests/integration/

  deploy:
    docker:
      - image: python:3.10
    steps:
      - checkout
      - run:
          name: Install deployment tools
          command: pip install --upgrade build setuptools wheel twine
      - run:
          name: Create the distribution files
          command: python -m build --sdist
      - run:
          name: Upload to PyPI
          command: twine upload --skip-existing dist/*

workflows:
  version: 2.1
  build-and-deploy:
    jobs:
      - build
      - integration
  tagged-deploy:
    jobs:
      - deploy:
          filters:
            tags:
              only: /[0-9]{4}.[0-9]{1,2}.[0-9]+/
            branches:
              ignore: /.*/
```

**After (GitHub Actions):**
```yaml
# build.yml
name: Build and Test

on:
  push:
    branches:
      - main
  pull_request:

jobs:
  build:
    environment: GH Actions
    permissions:
      contents: read
      id-token: write
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: '3.10'
          cache: 'pip'

      - name: Build venv and install dependencies
        run: |
          python3.10 -m venv venv/
          venv/bin/pip install -r requirements.txt

      - name: Ruff lint
        run: venv/bin/ruff check jetstream

      - name: Authenticate to GCP and Generate ID Token
        id: auth
        uses: google-github-actions/auth@v2
        with:
          workload_identity_provider: ${{ vars.GCPV2_GITHUB_WORKLOAD_IDENTITY_PROVIDER }}
          service_account: ${{ secrets.GCP_DRYRUN_SERVICE_ACCOUNT_EMAIL }}
          token_format: 'id_token'
          id_token_audience: 'https://us-central1-moz-fx-data-shared-prod.cloudfunctions.net/bigquery-etl-dryrun'
          id_token_include_email: true

      - name: Export ID Token for Python
        run: echo "GOOGLE_GHA_ID_TOKEN=${{ steps.auth.outputs.id_token }}" >> $GITHUB_ENV

      - name: PyTest
        run: venv/bin/pytest --ignore=tests/integration/

  integration:
    permissions:
      contents: read
      id-token: write
    environment: GH Actions
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: '3.10'
          cache: 'pip'

      - name: Build venv and install dependencies
        run: |
          python3.10 -m venv venv/
          venv/bin/pip install -r requirements.txt

      - name: Authenticate to GCP (OIDC)
        uses: google-github-actions/auth@v2
        with:
          workload_identity_provider: ${{ vars.GCPV2_GITHUB_WORKLOAD_IDENTITY_PROVIDER }}
          service_account: ${{ secrets.GCP_INTEGRATION_SERVICE_ACCOUNT_EMAIL }}

      - name: PyTest Integration Test
        run: venv/bin/pytest --integration tests/integration/
```

```yaml
# tagged-deploy.yml
name: Tagged Deploy

on:
  push:
    branches:
      - main
    tags:
      - '[0-9][0-9][0-9][0-9].[0-9]{1,2}.[0-9]+'

jobs:
  deploy:
    if: startsWith(github.ref, 'refs/tags/')
    permissions:
      contents: read
      id-token: write
    environment:
      name: pypi
      url: https://pypi.org/p/mozilla-jetstream
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: '3.10'

      - name: Install build dependencies
        run: pip install --upgrade build

      - name: Build distribution files
        run: python -m build --sdist

      - name: Publish distribution to PyPI
        uses: pypa/gh-action-pypi-publish@release/v1
```

---

### Example 3: Path Filtering with Multiple Validation Jobs

**Before (CircleCI):**
```yaml
# config.yml
version: 2.1
setup: true

orbs:
  path-filtering: circleci/path-filtering@1.3.0

workflows:
  filter-paths:
    jobs:
      - path-filtering/filter:
          base-revision: main
          config-path: .circleci/validation-config.yml
          mapping: |
            jetstream/.* validate-jetstream true
            definitions/.* validate-metrics true
            looker/.* validate-looker true

# validation-config.yml
version: 2.1

parameters:
  validate-jetstream:
    type: boolean
    default: false
  validate-metrics:
    type: boolean
    default: false

jobs:
  validate-jetstream:
    docker:
      - image: gcr.io/moz-fx-data-experiments/jetstream:latest
    steps:
      - checkout
      - run:
          name: Validate jetstream config files
          command: |
            changed_files=$(git diff --name-only main -- 'jetstream/*.toml')
            jetstream validate_config $changed_files

workflows:
  validate-jetstream:
    when: << pipeline.parameters.validate-jetstream >>
    jobs:
      - validate-jetstream
```

**After (GitHub Actions):**
```yaml
# changed-files.yml (reusable workflow)
name: Get changed files

on:
  workflow_call:
    inputs:
      path_filter:
        type: string
        required: false
        default: '**'
    outputs:
      any_changed:
        value: ${{ jobs.changed.outputs.any_changed }}
      all_changed_files:
        value: ${{ jobs.changed.outputs.all_changed_files }}

jobs:
  changed:
    runs-on: ubuntu-latest
    outputs:
      any_changed: ${{ steps.changed-files.outputs.any_changed }}
      all_changed_files: ${{ steps.changed-files.outputs.all_changed_files }}
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - uses: tj-actions/changed-files@v44
        id: changed-files
        with:
          files: ${{ inputs.path_filter }}
```

```yaml
# validate-jetstream.yml
name: Validate jetstream

on:
  pull_request:
    paths:
      - 'jetstream/**'
  push:
    branches:
      - main
    paths:
      - 'jetstream/**'

jobs:
  changed:
    uses: ./.github/workflows/changed-files.yml
    with:
      path_filter: |
        jetstream/**/*.toml

  validate-jetstream:
    runs-on: ubuntu-latest
    container:
      image: gcr.io/moz-fx-data-experiments/jetstream:latest
    needs: changed
    permissions:
      contents: read
      id-token: write
    if: needs.changed.outputs.any_changed == 'true'
    steps:
      - uses: actions/checkout@v4
        with:
          ref: ${{ github.head_ref }}

      - name: Set safe directory
        run: git config --global --add safe.directory "$GITHUB_WORKSPACE"

      - name: Authenticate to GCP
        uses: google-github-actions/auth@v2
        id: auth
        with:
          workload_identity_provider: ${{ vars.GCPV2_GITHUB_WORKLOAD_IDENTITY_PROVIDER }}
          service_account: ${{ secrets.GCP_DRYRUN_SERVICE_ACCOUNT_EMAIL }}
          token_format: id_token
          id_token_audience: https://us-central1-moz-fx-data-shared-prod.cloudfunctions.net/bigquery-etl-dryrun
          id_token_include_email: true

      - name: Export ID Token for Python
        env:
          GOOGLE_GHA_ID_TOKEN: ${{ steps.auth.outputs.id_token }}
        run: echo "GOOGLE_GHA_ID_TOKEN=$GOOGLE_GHA_ID_TOKEN" >> $GITHUB_ENV

      - name: Validate jetstream config files
        env:
          ALL_CHANGED_FILES: ${{ needs.changed.outputs.all_changed_files }}
        run: |
          echo "Run validation on changed files: $ALL_CHANGED_FILES"
          jetstream validate_config --config_repos='.' $ALL_CHANGED_FILES
```

---

## Need Help?

- CircleCI to GitHub Actions migration tool: https://github.com/mozilla/circleci-to-gha
- Mozilla GitHub Workflows & Actions Security: https://wiki.mozilla.org/GitHub/Repository_Security/GitHub_Workflows_%26_Actions
- GitHub Actions documentation: https://docs.github.com/en/actions
- PyPI Trusted Publishing guide: https://packaging.python.org/en/latest/guides/publishing-package-distribution-releases-using-github-actions-ci-cd-workflows/
