# CircleCI to GitHub Actions Migration Tool

AI-powered tool to migrate CircleCI configurations to GitHub Actions, following Mozilla's specific patterns and requirements.

## Features

- 🤖 **AI-Powered Migration** - Uses Google Gemini to intelligently convert CircleCI configs
- 🎯 **Mozilla-Specific Patterns** - Follows Mozilla's GAR, OIDC, and Workload Identity standards
- 📋 **Migration Checklists** - Generates comprehensive checklists for infrastructure changes
- 🔍 **Configuration Analysis** - Analyzes CircleCI configs and provides migration plans
- 🗑️ **Automatic Cleanup** - Optionally removes CircleCI configs after migration
- 📁 **Smart Output** - Automatically saves workflows to the repository's `.github/workflows/` directory

## Installation

```bash
# Clone the repository
git clone https://github.com/your-org/circleci-to-gha.git
cd circleci-to-gha

# Install in development mode
pip install -e .
```

## Prerequisites

### Google Cloud Configuration

This tool uses Google Vertex AI (Gemini) for AI-powered migrations:

```bash
circleci-to-gha generate --project-id mozdata --location global
```

### Authentication

Authenticate with Google Cloud:

```bash
gcloud auth application-default login
```

---

## Usage

### Main Command: `migrate`

The `migrate` command analyzes CircleCI configs and generates GitHub Actions workflows in one step:

```bash
# Migrate repo in current directory (writes files by default)
circleci-to-gha migrate

# Preview without writing files
circleci-to-gha migrate --no-write

# Migrate specific repo
circleci-to-gha migrate --repo /path/to/repo

# Migrate and remove CircleCI config
circleci-to-gha migrate --remove-circleci

# Custom output directory
circleci-to-gha migrate --output /custom/path
```

**What it does:**
1. 📊 Analyzes all CircleCI configs in `.circleci` directory
2. ⚙️ Generates GitHub Actions workflows
3. 💾 Saves workflows to `.github/workflows/` (unless `--no-write`)
4. Shows detailed migration analysis and generated files

**Example Output:**

```
Found 2 CircleCI configs:
  1. config.yml
  2. config-nightly.yml

================================================================================
Processing config.yml
================================================================================

📊 Analyzing config.yml...

Migration Analysis:
[Analysis details...]

⚙️ Generating workflows from config.yml...

✓ Workflows saved to /Users/anna/mydata/mozanalysis/.github/workflows
  - build.yml
  - deploy.yml
  - test.yml

================================================================================
✓ Migration complete!
================================================================================
```

---

### Additional Commands

#### Generate Migration Checklist

Get a detailed checklist for the migration:

```bash
# Generate checklist for current directory
circleci-to-gha checklist

# Generate checklist for specific repo
circleci-to-gha checklist --repo /path/to/repo

# Save to file
circleci-to-gha checklist > MIGRATION_CHECKLIST.md
```

**Output:**
- [ ] Repository secrets to configure
- [ ] Infrastructure changes needed (with specific file/line references)
- [ ] Workflow files to create
- [ ] Manual verification steps
- [ ] Testing recommendations

#### Generate dataservices-infra PR Content

Generate PR content for adding GAR access:

```bash
circleci-to-gha infra-pr mozanalysis
```

**Output:**
```markdown
## Add GAR access for mozanalysis

This PR adds the `mozanalysis` repository to the list of repositories
that can push images to Google Artifact Registry.

### Changes
- Added `mozanalysis` to the repository list in `data-artifacts/tf/prod/locals.tf`

### Testing
- [ ] Terraform plan shows expected changes
- [ ] No other resources affected

Related to CircleCI → GitHub Actions migration.
```

---

## Complete Migration Workflow

Here's a step-by-step guide for migrating a repository:

### Step 1: Preview the Migration

```bash
cd /path/to/your/repo
circleci-to-gha migrate --no-write
```

This will show you:
- Migration analysis and complexity assessment
- Generated workflows (preview only, no files written)
- Required infrastructure changes
- What secrets need to be configured

### Step 2: Generate Migration Checklist (Optional)

```bash
circleci-to-gha checklist > MIGRATION_CHECKLIST.md
```

Save the checklist for tracking migration progress.

### Step 3: Create Infrastructure PR (if needed)

If the analysis indicates Docker builds or Airflow DAG triggers:

```bash
# Generate PR content
circleci-to-gha infra-pr your-repo-name > infra-pr-content.md

# Create PR in dataservices-infra
# Follow the instructions in the generated PR content
```

### Step 4: Configure Repository Secrets

Based on the analysis, configure required secrets in GitHub:

1. Go to your repository → Settings → Secrets and variables → Actions
2. Add required secrets:
   - `GCP_SERVICE_ACCOUNT_EMAIL`
   - `GCP_DRYRUN_SERVICE_ACCOUNT_EMAIL` (if needed)
   - Any other secrets identified in the checklist

### Step 5: Generate Final Workflows

```bash
# Generate and save workflows
circleci-to-gha migrate

# Or remove CircleCI config in one step
circleci-to-gha migrate --remove-circleci
```

### Step 6: Test on a Branch

```bash
# Create a migration branch
git checkout -b circleci-to-gha-migration

# Commit the new workflows
git add .github/
git commit -m "Migrate from CircleCI to GitHub Actions"

# Push and create PR
git push origin circleci-to-gha-migration
```

### Step 8: Test in GitHub

Before merging, test the workflows to ensure they work correctly:

#### A. View Workflow Files in GitHub

1. Go to your PR on GitHub
2. Review the `.github/workflows/*.yml` files in the "Files changed" tab
3. Check for any syntax errors or issues flagged by GitHub

#### B. Test Workflow Triggers

The workflows will automatically run based on their triggers. Common scenarios:

**For Pull Request Workflows:**
```bash
# The PR itself will trigger workflows with:
# on:
#   pull_request:

# Check the "Actions" tab to see workflows running
```

**For Path-Based Workflows:**
```bash
# Make a change to a file that should trigger the workflow
echo "# test" >> relevant-file.py
git add relevant-file.py
git commit -m "Test workflow trigger"
git push origin circleci-to-gha-migration

# Check Actions tab - only workflows matching the changed paths should run
```

**For Push to Main Workflows:**
```bash
# These won't run on the PR branch
# After merging, check the Actions tab on main branch
```

#### C. Monitor Workflow Runs

1. Go to the **Actions** tab in your repository
2. Click on a running/completed workflow
3. Review each job and step for:
   - ✅ Authentication success (GCP, Docker, etc.)
   - ✅ Checkout working correctly
   - ✅ Dependencies installing properly
   - ✅ Tests passing
   - ✅ Docker builds succeeding (if applicable)
   - ⚠️ Any warnings or failures

#### D. Test Specific Scenarios

**Test Docker Build (if applicable):**
```bash
# Add a small change to trigger Docker build
echo "# trigger build" >> Dockerfile
git add Dockerfile
git commit -m "Test Docker build workflow"
git push origin circleci-to-gha-migration

# Check Actions tab for Docker build job
# Verify it doesn't try to push (should only push on main)
```

**Test with workflow_dispatch (Manual Trigger):**

If you want to test workflows without code changes, add `workflow_dispatch` temporarily:

```yaml
# In .github/workflows/your-workflow.yml
on:
  pull_request:
  workflow_dispatch:  # Enables manual triggering
```

Then:
1. Go to Actions tab
2. Select your workflow
3. Click "Run workflow" dropdown
4. Choose your branch
5. Click "Run workflow" button

#### E. Common Testing Issues

**Workflows Not Running:**
- Check that workflow triggers match your branch/changes
- Verify `.github/workflows/` directory path is correct
- Check for YAML syntax errors (GitHub will show these in PR)

**Authentication Failures:**
```
Error: Failed to authenticate to GCP
```
- Verify repository secrets are configured
- Check service account has correct permissions
- Confirm Workload Identity Federation is set up

**Permission Errors:**
```
Error: Resource not accessible by integration
```
- Add required permissions to workflow file:
```yaml
permissions:
  contents: read
  id-token: write
  pull-requests: write  # If commenting on PRs
```

**Docker Push Failures:**
```
Error: denied: Permission "artifactregistry.repositories.uploadArtifacts" denied
```
- Ensure dataservices-infra PR is merged
- Verify service account has GAR permissions
- Check that `if: github.ref == 'refs/heads/main'` is protecting push steps

#### F. Dry Run Testing

For workflows that push or deploy, verify protection:

```yaml
# Check that dangerous operations only run on main
- name: Push Docker image
  if: github.ref == 'refs/heads/main'  # Should NOT run on PR
  uses: mozilla-it/deploy-actions/docker-push@v4.3.2
```

#### G. Enable Debug Logging

If workflows fail, enable debug logging:

1. Go to repository Settings → Secrets and variables → Actions
2. Add repository variable:
   - Name: `ACTIONS_STEP_DEBUG`
   - Value: `true`
3. Re-run the workflow

Or add temporarily to workflow:

```yaml
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - name: Debug info
        run: |
          echo "GitHub ref: ${{ github.ref }}"
          echo "GitHub event: ${{ github.event_name }}"
          echo "GitHub actor: ${{ github.actor }}"
```

#### H. Workflow Status Badges

Add status badges to PR description to track progress:

```markdown
## Workflow Status

![Build](https://github.com/mozilla/repo-name/actions/workflows/build.yml/badge.svg?branch=circleci-to-gha-migration)
![Test](https://github.com/mozilla/repo-name/actions/workflows/test.yml/badge.svg?branch=circleci-to-gha-migration)
```

#### I. Final Checklist Before Merge

- [ ] All workflows run successfully on PR
- [ ] No authentication errors
- [ ] Tests pass
- [ ] Docker builds succeed (if applicable)
- [ ] No secrets exposed in logs
- [ ] Protected operations only run on main (check `if:` conditions)
- [ ] Path filtering works correctly
- [ ] Reusable workflows function properly
- [ ] PR comments/automation work (if applicable)
- [ ] CircleCI workflows disabled or removed

### Step 9: Clean Up (Optional)

After verifying the GitHub Actions workflows work on main:

```bash
# Remove CircleCI config
rm -rf .circleci/

# Commit and push
git add .circleci/
git commit -m "Remove CircleCI configuration"
git push origin main
```

---

## Command Reference

### Global Options

```bash
--project-id TEXT       Google Cloud Project ID (default: mozdata, env: GOOGLE_CLOUD_PROJECT)
--location TEXT         Google Cloud Location (default: global, env: GOOGLE_CLOUD_LOCATION)
```

### Commands

#### `migrate`

Analyze and generate GitHub Actions workflows in one step.

```bash
circleci-to-gha migrate [OPTIONS]

Options:
  -r, --repo PATH       Path to repository to migrate (default: current directory)
  -o, --output PATH     Output directory (default: <repo>/.github/workflows)
  --project-id TEXT     Google Cloud Project ID (default: mozdata)
  --location TEXT       Google Cloud Location (default: global)
  --write/--no-write    Write generated workflows to files (default: write)
  --remove-circleci     Remove CircleCI config directory after generating
  --help                Show this message and exit
```

**Note:** Automatically discovers all CircleCI configs in the `.circleci` directory.

#### `checklist`

Generate migration checklist.

```bash
circleci-to-gha checklist [OPTIONS]

Options:
  -r, --repo PATH    Path to repository to migrate (default: current directory)
  --project-id TEXT  Google Cloud Project ID (default: mozdata)
  --location TEXT    Google Cloud Location (default: global)
  --help             Show this message and exit
```

**Note:** Generates checklists for all CircleCI configs found in the `.circleci` directory.

#### `infra-pr`

Generate dataservices-infra PR content for GAR access.

```bash
circleci-to-gha infra-pr REPO_NAME

Arguments:
  REPO_NAME  Repository name to add to GAR access list

Options:
  --help     Show this message and exit
```

---

## Examples

### Example 1: Simple Repository Migration

```bash
# Navigate to repository
cd ~/projects/my-mozilla-repo

# Preview migration (doesn't write files)
circleci-to-gha migrate --no-write

# Generate workflows and remove CircleCI config
circleci-to-gha migrate --remove-circleci
```

### Example 2: Complex Migration with Custom Settings

```bash
# Use specific project and location with preview
circleci-to-gha migrate \
  --repo /path/to/complex-repo \
  --project-id moz-fx-data-shared-prod \
  --location us-central1 \
  --no-write

# Generate to custom location
circleci-to-gha migrate \
  --repo /path/to/complex-repo \
  --output /tmp/workflows
```

### Example 3: Multiple Repositories

```bash
# Script to migrate multiple repos
for repo in repo1 repo2 repo3; do
  echo "Migrating $repo..."
  cd ~/projects/$repo
  circleci-to-gha migrate
  circleci-to-gha infra-pr $repo > ~/migrations/$repo-infra-pr.md
done
```

---

## Troubleshooting

### Authentication Issues

If you see authentication errors:

```bash
# Re-authenticate with gcloud
gcloud auth application-default login

# Verify credentials
gcloud auth application-default print-access-token
```

### Missing Environment Variables

```bash
# Check if variables are set
echo $GOOGLE_CLOUD_PROJECT
echo $GOOGLE_CLOUD_LOCATION

# Set if missing
export GOOGLE_CLOUD_PROJECT=mozdata
export GOOGLE_CLOUD_LOCATION=global
```

### Tool Not Found

If `circleci-to-gha` command is not found:

```bash
# Add to PATH
export PATH="$HOME/.local/bin:$PATH"

# Or reinstall
pip install -e . --force-reinstall
```

---

## What Gets Generated

The tool generates production-ready GitHub Actions workflows following Mozilla's standards:

### Workflow Features

- ✅ **OIDC Authentication** - Workload Identity Federation for GCP
- ✅ **GAR Integration** - Proper Docker image push patterns
- ✅ **Secrets Management** - Repository secrets and variables
- ✅ **Path Filtering** - Conditional workflow execution based on file changes
- ✅ **Reusable Workflows** - For common patterns like changed file detection
- ✅ **Proper Permissions** - Minimal required permissions per job
- ✅ **Caching** - Python pip caching and custom cache patterns
- ✅ **Container Jobs** - For jobs requiring specific Docker images
- ✅ **PR Automation** - Comments, reviews, and status checks

### Infrastructure Awareness

The tool identifies when additional infrastructure changes are needed:

- **GAR Access** - Detects Docker builds and notes dataservices-infra PR requirements
- **Service Accounts** - Lists required GCP service accounts
- **Airflow DAG Triggers** - Detects and converts Airflow triggering patterns
- **GKE Operations** - Converts Kubernetes operations properly

---

## Contributing

### Development Setup

```bash
# Install development dependencies
pip install -e ".[dev]"

# Run linting
ruff check circleci_to_gha/
ruff format --check circleci_to_gha/
```

### Project Structure

```
circleci_to_gha/
├── __init__.py           # Package initialization
├── cli.py                # CLI interface
├── ai_client.py          # Gemini AI client
├── config_parser.py      # CircleCI config parser
├── generator.py          # Workflow generation
└── prompts/
    ├── __init__.py       # Prompts package
    ├── system_prompt.txt # AI system prompt with Mozilla patterns
    └── examples.txt      # Real-world migration examples
```

---


## Support

For issues or questions:
- Create an issue in this repository
- Reach out to the Data Engineering team

---

## Related Resources

- [Mozilla dataservices-infra](https://github.com/mozilla/dataservices-infra)
- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Mozilla CI/CD Guidelines](https://wiki.mozilla.org/)