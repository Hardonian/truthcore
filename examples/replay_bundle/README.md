# Replay Bundle Example

This directory contains an example replay bundle for demonstration and testing.

## Structure



## Usage

### Replay the bundle



### Run simulation



### Export a new bundle



## Expected Results

The example bundle represents a UI analysis that found:
- 1 HIGH severity issue (button not clickable)
- 1 MEDIUM severity issue (TypeScript warning)
- 1 LOW severity issue (missing security header)

Total: 60 points (exceeds threshold of 100 in strict mode, but within PR limits)

With the example changes:
- UI weight reduced to 0.5
- UI geometry engine disabled
- UI_001 finding suppressed

The simulated verdict should show improved results.
