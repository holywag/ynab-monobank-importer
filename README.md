# YNAB Transaction Importer

Pipeline-based tool for importing bank transactions into [YNAB](https://www.ynab.com/). Reads from bank APIs or parsed statements, maps payees and categories, deduplicates transfers, and uploads to YNAB.

## Quick start

```bash
git submodule update -f --recursive --init
pip install $(ls -d api/*) -r ./requirements.txt
```

Create a `.env` file with your tokens (git-ignored):

```
MONO_TOKEN=your_monobank_api_token
YNAB_TOKEN=your_ynab_personal_access_token
```

Run:

```bash
python src/main.py
```

## How it works

Everything is driven by a **pipeline** defined in YAML. A pipeline is a sequence of steps that process a stream of transactions:

```yaml
# config/pipelines/daily_import.yaml
steps:
  - read:
      from:
        monobank.checking: my_budget.Checking Account
      time_range:
        start: "2025-01-01T00:00:00+02:00"

  - map:
      type: payee
      mappings: config/mappings/payees.yaml

  - map:
      type: categorize
      mappings: config/mappings/categories.yaml

  - filter: deduplicate_transfers

  - write:
      to: my_budget
```

Each step transforms the transaction stream: **read** creates it from bank sources, **map** modifies transactions, **filter** removes some, and **write** sends them to YNAB.

## Supported banks

| Bank | Method |
|-|-|
| Monobank | REST API via [wrapper](https://github.com/holywag/mono-api.git) |
| PUMB | PDF parsing |
| ABank | PDF parsing |
| PrivatBank | PDF parsing |
| SenseBank | CSV parsing |
| Millennium bcp | PDF parsing (with EUR/UAH conversion) |

## Configuration

### File structure

```
config/
  config.yaml               # Main config — references other files
  sources.yaml               # Bank connections and accounts
  budgets.yaml               # YNAB budget definitions
  mappings/
    payees.yaml              # Payee name aliases (regex-based)
    categories.yaml          # Auto-categorization rules
  pipelines/
    daily_import.yaml        # Pipeline definition
.env                         # Secrets (git-ignored)
```

### `config.yaml` — entry point

References other config files. `sources` and `budgets` accept either a file path or inline content:

```yaml
sources: config/sources.yaml
budgets: config/budgets.yaml

# or inline:
budgets:
  my_budget:
    token: "${YNAB_TOKEN}"
    budget: "My Budget"

pipelines:
  daily_import: config/pipelines/daily_import.yaml
```

### `sources.yaml` — bank connections

Each source defines a bank type, credentials, and accounts. Tokens use `${ENV_VAR}` syntax:

```yaml
monobank:
  type: monobank
  token: "${MONO_TOKEN}"
  retries: 5
  remove_cancelled: true
  accounts:
    checking:
      iban: "UA663220010000026201234567890"
      transfer_patterns:        # regex patterns to detect transfers to this account
        - 'From checking'

# File-based sources (PDF/CSV parsing)
pumb:
  type: pumb_credit
  path: "/path/to/bank/statements"
  accounts:
    credit:
      iban: "UA583220010000026001234567890"

# Tracking accounts — no bank API, used for transfer detection only
tracking:
  type: tracking
  accounts:
    cash: {}
```

**Source types**: `monobank`, `pumb`, `pumb_credit`, `sensebank`, `abank`, `privatbank`, `millennium`, `tracking`.

### Pipeline steps

#### `read` — fetch transactions from bank sources

```yaml
- read:
    from:                                         # accounts to fetch
      monobank.checking: my_budget.Checking       # source.account: budget.ynab_account
    tracking:                                     # transfer detection only (not fetched)
      monobank.savings: my_budget.Savings
    time_range:
      start: "2025-01-01T00:00:00+02:00"         # ISO datetime
      # start: config/timestamp                   # or file containing bare ISO string
```

#### `map` — transform transactions

Built-in mappers:

```yaml
# Rename bank descriptions to clean payee names
- map:
    type: payee
    mappings: config/mappings/payees.yaml

# Auto-categorize by payee regex or MCC code
- map:
    type: categorize
    mappings: config/mappings/categories.yaml
```

#### `filter` — remove transactions

```yaml
- filter: deduplicate_transfers   # remove duplicate sides of inter-account transfers
```

#### `write` — upload to YNAB

```yaml
- write:
    to: my_budget
    timestamp: config/timestamp   # optional: save current time after successful upload
```

When `timestamp` is set, the file is written with a bare ISO datetime string on success. This pairs with `time_range.start` reading from the same file for incremental imports.

### Mapping files

**Payees** — map messy bank descriptions to clean names (regex):

```yaml
Apple:
  - 'APPLE\.COM'
Netflix:
  - 'NETFLIX\.COM'
  - 'Netflix'
```

**Categories** — auto-categorize by payee pattern or MCC code:

```yaml
- category:
    group: Everyday
    name: Groceries
  match:
    mcc: [5411, 5422]
    payee: ['LIDL', 'Silpo']
```

Priority: payee match first, then MCC. Unmatched transactions are left uncategorized.

## Extending

The pipeline is designed for extensibility. Two extension points:

### Custom map/filter steps

Register new callables in `src/pipeline/steps.py`:

```python
@register_mapper('my_transform')
class MyTransform:
    def __init__(self, some_param: str, **kwargs):
        self.param = some_param

    def __call__(self, t: YnabTransaction) -> YnabTransaction:
        # modify t
        return t
```

Then use in pipeline YAML:

```yaml
- map:
    type: my_transform
    some_param: value
```

Filters work the same way with `@register_filter` — return `True` to keep, `False` to drop.

### Custom transaction sources

Implement `YnabTransactionSource` in `src/sources/`:

```python
class MySource(YnabTransactionSource):
    def read(self) -> Iterable[YnabTransaction]:
        ...
```

Wire it into the read step builder in `src/pipeline/steps.py`. See `BankApiSource` for the pattern.
