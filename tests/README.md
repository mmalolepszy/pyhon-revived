# Test suite

This directory contains the pyhon-revived test suite.

## Layout

- `test_appliance.py` — unit tests for `HonAppliance` attribute access
  (regression tests for the dotted-key bug fixed in commit `552127a`).
- `test_integration.py` — parametrized integration tests that load
  every appliance in `tests/hon-test-data/test_data/` and verify it
  parses without crashing.
- `conftest.py` — shared fixtures for loading the test data.
- `hon-test-data/` — git submodule pointing to
  https://github.com/mmalolepszy/hon-test-data, a community-maintained
  collection of anonymized appliance exports.

## Running the tests

```bash
# Clone with the submodule
git clone --recurse-submodules ssh://git@ade.alele.lan:2222/odyno/pyhon-revived.git
cd pyhon-revived

# Or if you already cloned without submodules
git submodule update --init --recursive

# Create a virtualenv and install dev dependencies
uv venv
source .venv/bin/activate

# Install pyhon in editable mode (required for tests to find the package)
uv pip install -e .
uv pip install -r requirements_dev.txt

# Run everything
pytest

# Run only the integration tests (one per appliance in test_data)
pytest tests/test_integration.py -v

# Run only the unit tests
pytest tests/test_appliance.py -v
```

Expected result: **215 passed, 4 skipped** (the 4 skipped are for
`td_144`, whose `appliance_data.json` is malformed upstream).

## Adding your own appliance data

If your device is not yet covered, or you want to test against your
exact model:

```bash
# 1. Activate the pyhon virtualenv
source .venv/bin/activate

# 2. Export your data anonymized (serial numbers, MACs, dates are masked)
python -m pyhon export --anonymous tests/hon-test-data/test_data/

# 3. The previous command creates one directory per appliance, e.g.
#    tests/hon-test-data/test_data/ac_1234/
#    tests/hon-test-data/test_data/ov_5678/

# 4. Commit the new directories and push the submodule update
cd tests/hon-test-data
git add .
git commit -m "Add my Haier AC AS35TEDHRA(M1) data"
git push  # you may need to fork hon-test-data first

# 5. Back in pyhon-revived, commit the submodule pointer update
cd ../..
git add tests/hon-test-data
git commit -m "chore: update hon-test-data submodule with my appliance"
```

The integration tests are parametrized over every directory found in
`test_data/`, so your new appliance will be picked up automatically on
the next `pytest` run — no code changes needed.

## CI

The GitHub Actions workflow runs `pytest` on every PR. Make sure the
submodule is checked out (`actions/checkout` with `submodules: true`).
