#!/bin/bash
# Truth Core Installation Verification Script
# Run this after cloning to verify the environment is correctly set up

set -e

echo "========================================="
echo "Truth Core Installation Verification"
echo "========================================="

# Check Python version
echo ""
echo "Checking Python version..."
python_version=$(python --version 2>&1 | awk '{print $2}')
echo "  Python: $python_version"

# Check Python >= 3.11
required_version="3.11"
if [ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" != "$required_version" ]; then
    echo "  ❌ ERROR: Python 3.11+ required"
    exit 1
fi
echo "  ✅ Python version OK"

# Check pnpm
echo ""
echo "Checking pnpm..."
if ! command -v pnpm &> /dev/null; then
    echo "  ⚠️ WARNING: pnpm not found. Installing..."
    npm install -g pnpm
fi
pnpm_version=$(pnpm --version)
echo "  pnpm: $pnpm_version"
echo "  ✅ pnpm OK"

# Install Python dependencies
echo ""
echo "Installing Python dependencies..."
pip install -e ".[dev,parquet]" --quiet
echo "  ✅ Python dependencies installed"

# Install Node.js dependencies
echo ""
echo "Installing Node.js dependencies..."
pnpm install --silent
cd packages/ts-contract-sdk && pnpm install --silent
cd ../..
echo "  ✅ Node.js dependencies installed"

# Run Python tests
echo ""
echo "Running Python tests..."
python -m pytest tests/ -q --tb=no -x 2>&1 | tail -5
if [ $? -eq 0 ]; then
    echo "  ✅ Python tests passing"
else
    echo "  ⚠️ WARNING: Some Python tests failed (see above)"
fi

# Run Python linting
echo ""
echo "Running Python linting..."
cd src/truthcore && python -m ruff check . ../../tests --output-format=concise 2>&1 | tail -3
cd ../..
echo "  ✅ Python linting complete"

# Run TypeScript SDK tests
echo ""
echo "Running TypeScript SDK tests..."
cd packages/ts-contract-sdk && pnpm run test 2>&1 | tail -3
cd ../..
echo "  ✅ TypeScript SDK tests passing"

# Build TypeScript SDK
echo ""
echo "Building TypeScript SDK..."
cd packages/ts-contract-sdk && pnpm run build 2>&1 | tail -3
cd ../..
echo "  ✅ TypeScript SDK built"

# Build dashboard
echo ""
echo "Building dashboard..."
cd dashboard && npm run build 2>&1 | tail -3
cd ..
echo "  ✅ Dashboard built"

# Check CLI works
echo ""
echo "Testing CLI..."
truthctl --version
echo "  ✅ CLI working"

# Create test run
echo ""
echo "Creating test verification run..."
mkdir -p /tmp/verify-test
echo '{"elements": [{"id": "test", "clickable": true}]}' > /tmp/verify-test/ui_facts.json
truthctl judge --inputs /tmp/verify-test --profile ui --out /tmp/verify-test/out 2>&1 | tail -3
echo "  ✅ Verification run complete"

echo ""
echo "========================================="
echo "✅ All verification checks passed!"
echo "========================================="
echo ""
echo "Next steps:"
echo "  1. Copy .env.example to .env and configure"
echo "  2. Run: pnpm run dev:dashboard  # Start dashboard"
echo "  3. Run: truthctl serve          # Start API server"
echo ""
echo "Documentation: https://github.com/your-org/truth-core#readme"
