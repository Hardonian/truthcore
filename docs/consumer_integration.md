# Consumer Integration Guide

This guide explains how to integrate truth-core into your projects and pin to specific contract versions.

## Overview

truth-core produces versioned artifacts that your CI/CD pipelines can consume. This guide shows you how to:
- Pin to specific contract versions
- Validate truth-core outputs
- Handle contract version upgrades

## Pinning to Contract Versions

### Why Pin?

Pinning to a specific contract version ensures:
- **Stability**: Your code won't break when truth-core releases new versions
- **Predictability**: You control when to upgrade
- **Validation**: You can validate artifacts match expected schemas

### How to Pin

#### Method 1: CI Validation (Recommended)

Add a validation step in your CI that checks the contract version:

```yaml
# .github/workflows/ci.yml
jobs:
  truth-core:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Install truth-core
        run: pip install truth-core
      
      - name: Run truth-core
        run: truthctl judge --inputs ./src --out ./truth-outputs
      
      - name: Validate contract version
        run: |
          CONTRACT_VERSION=$(jq -r '._contract.contract_version' ./truth-outputs/verdict.json)
          if [ "$CONTRACT_VERSION" != "2.0.0" ]; then
            echo "Expected contract version 2.0.0, got $CONTRACT_VERSION"
            exit 1
          fi
      
      - name: Validate artifact
        run: truthctl contracts validate --file ./truth-outputs/verdict.json --strict
```

#### Method 2: Compat Mode

Request a specific output version:

```bash
# Always get version 1.0.0 format
truthctl judge --inputs ./src --out ./truth-outputs --compat 1.0.0
```

This works even if truth-core is newer - it will convert outputs to the requested version.

#### Method 3: Dependency Pinning

Pin the truth-core version in your requirements:

```txt
# requirements.txt
truth-core==0.2.0  # Produces contract version 2.0.0
```

## Handling Version Upgrades

### When truth-core Announces a New Contract Version

1. **Review the changelog** for breaking changes
2. **Test in staging** before production
3. **Update your code** to handle new fields
4. **Pin to the new version** once validated

### Example Upgrade Path

```bash
# Step 1: Check current version
$ truthctl contracts list
verdict: 2.0.0 (current), 1.0.0 (supported)

# Step 2: Migrate old artifacts if needed
$ truthctl contracts migrate --file old_verdict.json --to 2.0.0 --out new_verdict.json

# Step 3: Validate your consumer code with new format
# (Run your tests)

# Step 4: Update your CI to pin to new version
# (Update the version check in your workflow)
```

## Validation in Production

Always validate artifacts before consuming them:

```python
import json
from truthcore.contracts.validate import validate_artifact_or_raise

# Load artifact
with open("verdict.json") as f:
    artifact = json.load(f)

# Validate against expected version
try:
    validate_artifact_or_raise(artifact, "verdict", "2.0.0", strict=True)
    print("Valid - proceed with processing")
except ValidationError as e:
    print(f"Invalid artifact: {e}")
    # Handle error - don't process
```

## Contract Version Compatibility

truth-core supports the last 2 MAJOR versions:

| truth-core Version | Default Contract | Supported Versions |
|-------------------|------------------|-------------------|
| 0.2.x | 2.0.0 | 1.x.x, 2.x.x |
| 0.1.x | 1.0.0 | 1.x.x |

## Best Practices

1. **Pin to MAJOR.MINOR** (e.g., "2.0") for stability while getting patches
2. **Validate in CI** before merging changes
3. **Test migrations** before upgrading
4. **Monitor deprecation notices** in CHANGELOG
5. **Use compat mode** during transition periods

## Troubleshooting

### "Unknown contract version" Error

Your truth-core version doesn't recognize the artifact version. Upgrade truth-core:

```bash
pip install --upgrade truth-core
```

### "Validation failed" Error

The artifact doesn't match the schema. Check:
- Is the artifact corrupted?
- Are you using the right schema version?
- Run with `--strict` to catch extra fields

### Migration Not Found

No migration path exists between versions. You may need to:
- Upgrade truth-core to a version with the migration
- Handle both versions in your consumer code
- Contact truth-core maintainers

## Example Integration: Python Consumer

```python
from truthcore.contracts import extract_metadata, validate_artifact_or_raise
import json

class TruthCoreConsumer:
    """Example consumer that pins to contract version 2.0.0."""
    
    SUPPORTED_VERSION = "2.0.0"
    
    def process_verdict(self, artifact_path: str) -> dict:
        # Load artifact
        with open(artifact_path) as f:
            artifact = json.load(f)
        
        # Extract metadata
        metadata = extract_metadata(artifact)
        if not metadata:
            raise ValueError("No contract metadata found")
        
        # Check version compatibility
        if metadata.contract_version != self.SUPPORTED_VERSION:
            raise ValueError(
                f"Expected version {self.SUPPORTED_VERSION}, "
                f"got {metadata.contract_version}"
            )
        
        # Validate
        validate_artifact_or_raise(artifact, "verdict", self.SUPPORTED_VERSION)
        
        # Process (your logic here)
        return {
            "verdict": artifact["verdict"],
            "value": artifact["value"],
            "confidence": artifact["confidence"],
        }
```

## Example Integration: JavaScript Consumer

```javascript
// Example Node.js consumer
const fs = require('fs');

const SUPPORTED_VERSION = '2.0.0';

function processVerdict(artifactPath) {
  // Load artifact
  const artifact = JSON.parse(fs.readFileSync(artifactPath, 'utf8'));
  
  // Extract metadata
  const metadata = artifact._contract;
  if (!metadata) {
    throw new Error('No contract metadata found');
  }
  
  // Check version
  if (metadata.contract_version !== SUPPORTED_VERSION) {
    throw new Error(
      `Expected version ${SUPPORTED_VERSION}, got ${metadata.contract_version}`
    );
  }
  
  // Process (your logic here)
  return {
    verdict: artifact.verdict,
    value: artifact.value,
    confidence: artifact.confidence,
  };
}
```

## See Also

- [Contracts Guide](../contracts.md) - Contract system documentation
- [Migration Guide](../migrations.md) - How to migrate artifacts
- [Versioning Policy](../versioning_policy.md) - Version governance rules
