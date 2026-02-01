# GitHub Actions Integration for Truth Core

Run truth-core verification in your GitHub Actions workflows with configurable profiles for different verification scenarios.

## Quick Start

Add truth-core verification to your workflow in 10 lines of YAML:

```yaml
- name: Run Truth Core Verification
  uses: your-org/truth-core/integrations/github-actions@main
  with:
    profile: readylayer
    inputs-path: ./src
```

## Usage Examples

### ReadyLayer (PR/CI Quality Checks)

For standard code quality verification in pull requests:

```yaml
name: PR Verification
on: [pull_request]

jobs:
  verify:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Truth Core Verification
        uses: your-org/truth-core/integrations/github-actions@main
        with:
          profile: readylayer
          inputs-path: ./src
          output-path: verdict.json
      
      - name: Upload Verdict
        uses: actions/upload-artifact@v4
        with:
          name: truthcore-verdict
          path: verdict.json
```

### Settler (Release Verification)

For pre-deployment readiness checks:

```yaml
name: Release Verification
on:
  push:
    tags:
      - 'v*'

jobs:
  verify:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Verify Release Readiness
        uses: your-org/truth-core/integrations/github-actions@main
        with:
          profile: settler
          inputs-path: ./
          sign-bundle: true
          signing-key: ${{ secrets.TRUTHCORE_SIGNING_KEY }}
```

### AIAS (AI Agent Trace Validation)

For validating AI agent traces:

```yaml
name: Agent Trace Verification
on: [push]

jobs:
  verify:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Validate Agent Traces
        uses: your-org/truth-core/integrations/github-actions@main
        with:
          profile: aias
          inputs-path: ./traces
          config: ./custom-aias-config.yaml
```

### Keys (Security Credential Verification)

For security and compliance checks:

```yaml
name: Security Verification
on:
  schedule:
    - cron: '0 0 * * 0'  # Weekly

jobs:
  verify:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Verify Security Keys
        uses: your-org/truth-core/integrations/github-actions@main
        with:
          profile: keys
          inputs-path: ./keys
          upload-artifacts: true
```

## Inputs

| Input | Description | Required | Default |
|-------|-------------|----------|---------|
| `profile` | Verification profile (readylayer, settler, aias, keys, custom) | No | `readylayer` |
| `config` | Path to custom config file | No | (profile default) |
| `inputs-path` | Path to inputs directory/files | Yes | - |
| `output-path` | Path for verdict output | No | `truthcore-verdict.json` |
| `upload-artifacts` | Upload artifacts | No | `true` |
| `sign-bundle` | Sign evidence bundle | No | `false` |
| `signing-key` | Path to signing key | No | - |
| `truthctl-version` | truth-core version | No | `latest` |
| `python-version` | Python version | No | `3.11` |

## Outputs

| Output | Description |
|--------|-------------|
| `verdict` | Overall verdict (PASS, FAIL, WARN, UNKNOWN) |
| `verdict-file` | Path to generated verdict file |
| `score` | Overall score (0-100) |
| `findings-count` | Number of findings |
| `artifact-id` | Artifact upload ID |

## Profiles

### ReadyLayer
- **Purpose**: Code quality and readiness for PR/CI
- **Focus**: Quality, coverage, security basics, documentation
- **Thresholds**: Pass ≥90, Warn ≥75, Fail <75

### Settler
- **Purpose**: Release and deployment verification
- **Focus**: Stability, performance, compatibility, rollback safety
- **Thresholds**: Pass ≥95, Warn ≥85, Fail <85

### AIAS
- **Purpose**: AI agent trace verification
- **Focus**: FSM validation, state transitions, safety bounds
- **Thresholds**: Pass ≥92, Warn ≥80, Fail <80

### Keys
- **Purpose**: Security key and credential verification
- **Focus**: Key validation, rotation, exposure detection
- **Thresholds**: Pass ≥98, Warn ≥90, Fail <90

## Custom Configuration

Create a custom config file and reference it:

```yaml
- name: Custom Verification
  uses: your-org/truth-core/integrations/github-actions@main
  with:
    profile: custom
    config: ./my-truthcore-config.yaml
    inputs-path: ./src
```

See profile configs in `configs/` directory for examples.

## License

MIT
