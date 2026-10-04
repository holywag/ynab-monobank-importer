# YNAB Transaction Importer

Pipeline-based tool for importing bank transactions into [YNAB](https://www.ynab.com/). Reads from bank APIs or parsed statements, maps payees and categories, deduplicates transfers, and uploads to YNAB.

## Quick start

```bash
git submodule update -f --recursive --init
pip install $(ls -d api/*) -r ./requirements.txt
```

Create a `.env` file with your tokens (git-ignored). The names must match the `${...}`
references in your `sources.yaml` / `budgets`:

```
YNAB_TOKEN=your_ynab_personal_access_token
```

Run:

```bash
python src/main.py
```

The pipeline to run is currently selected by editing `pipeline_name` in `src/main.py`
(CLI selection is a TODO). It must be a key under `pipelines` in `config.yaml`.

## How it works

Everything is driven by a **pipeline** defined in YAML. A pipeline is a sequence of steps that process a stream of transactions:

```yaml
# config/pipelines/daily_import.yaml
steps:
  - read_from:
      source:
        monobank.checking: my_budget.Checking Account   # source.account: budget.ynab_account
      time_range:
        start: "2025-01-01T00:00:00+02:00"

  - filter: deduplicate_transfers

  - map:
      type: categorize
      mappings: config/mappings/categories.yaml
      budget: my_budget

  - map:
      type: payee
      mappings: config/mappings/payees.yaml

  - write_to:
      ynab_api: my_budget
```

Each step transforms the transaction stream: **read_from** creates it (from bank sources or an existing YNAB budget), **map** modifies transactions, **filter** removes some, and **write_to** sends them to YNAB.

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
  config.yaml               # Main config — budgets + references to sources & pipelines
  sources.yaml              # Bank connections and accounts
  mappings/
    payees.yaml             # Payee name aliases (regex-based)
    categories.yaml         # Auto-categorization rules
  pipelines/
    daily_import.yaml       # Pipeline definitions (one file per pipeline)
  timestamp                 # Last-import marker (optional, written by write_to)
.env                        # Secrets (git-ignored)
```

### `config.yaml` — entry point

Defines budgets and references the other config files. `sources` and `budgets` accept
either a file path or inline content; `pipelines` maps a pipeline name to its YAML file:

```yaml
budgets:                              # inline, or: budgets: config/budgets.yaml
  my_budget:
    token: "${YNAB_TOKEN}"
    budget: "My Budget"           # YNAB budget display name

sources: config/sources.yaml          # path, or inline source definitions

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

# File-based sources (PDF/CSV parsing) — use `path` instead of a token
abank:
  type: abank
  path: "/path/to/bank/statements"
  orig_amount: false            # optional, abank only — use original-currency
                                # amount instead of the UAH amount
  accounts:
    abank:
      iban: "UA583220010000026001234567890"

# Tracking accounts — no bank API, used for transfer detection only
tracking:
  type: tracking
  accounts:
    cash: {}
```

Statements are discovered by globbing `<path>/<iban>/` recursively for the engine's file
type (e.g. `*.pdf`, `*.csv`).

**Source types**: `monobank`, `pumb`, `sensebank`, `abank`, `privatbank`, `ukrsibbank`, `millennium`, `tracking`. Filesystem sources take a `path`; `monobank` takes a `token` plus optional `retries` / `remove_cancelled`; `abank` additionally accepts `orig_amount`. (`ukrsibbank` has no parser yet and is only usable as a tracking source.)

### Pipeline steps

#### `read_from` — create the transaction stream

From bank sources:

```yaml
- read_from:
    source:                                       # accounts to fetch
      monobank.checking: my_budget.Checking       # source.account: budget.ynab_account
    tracking:                                     # transfer detection only (not fetched)
      monobank.savings: my_budget.Savings
    time_range:
      start: "2025-01-01T00:00:00+02:00"          # ISO datetime
      # start: ./config/timestamp                 # or path to a file holding a bare ISO string
      # end: "2025-06-01T00:00:00+02:00"          # optional
```

Or re-read already-imported transactions from a YNAB budget (useful for modifying/converting pipelines):

```yaml
- read_from:
    ynab_api:
      family:                                     # budget key
        - 🇪🇺 Cash                                 # YNAB account names to read
    time_range:
      start: "2024-09-24"
      end: "2026-06-02"
```

#### `map` — transform transactions

Built-in mappers (selected with `type:`):

| `type` | Purpose | Key params |
|-|-|-|
| `payee` | Rename bank descriptions to clean payee names (regex) | `mappings` |
| `categorize` | Assign category by payee regex or MCC code | `mappings`, `budget` |
| `change_date` | Rewrite the transaction year | `year` |
| `convert_to_uah_by_memo` | Convert a EUR amount stated in the memo to UAH | — |
| `migrate_to_eur` | Convert UAH transactions to EUR via a FIFO cost-basis model | — |
| `log` | Print selected fields (pass-through, for debugging) | `fields`, `format` |
| `progress_tracker` | Print a periodic processed-count (pass-through) | — |

```yaml
# Rename bank descriptions to clean payee names
- map:
    type: payee
    mappings: config/mappings/payees.yaml

# Auto-categorize by payee regex or MCC code
- map:
    type: categorize
    mappings: config/mappings/categories.yaml
    budget: family              # budget key used to resolve category IDs

# Debug printer. `fields.detail` lists TransactionDetail attributes; `format` is an
# optional template with positional `{}` placeholders (no attribute access allowed).
- map:
    type: log
    format: "{} {} {}\n{}"
    fields:
      detail:
        - account_name
        - payee_name
        - var_date
        - amount
```

#### `filter` — remove transactions

```yaml
- filter: deduplicate_transfers   # remove duplicate sides of inter-account transfers
```

A mapper that also defines a `filter` method (e.g. `fix_amount`) can be used in a
`filter:` step too.

#### `write_to` — upload to YNAB

```yaml
- write_to:
    ynab_api: my_budget           # destination budget key
    timestamp: config/timestamp   # optional: save current time after successful upload
```

Transactions are created or updated in bulk. When the source budget differs from the
destination, account/category/transfer references are re-mapped by name. When `timestamp`
is set, the file is written with a bare ISO datetime string on success — this pairs with
`time_range.start` reading from the same file for incremental imports.

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

Register a class with `@register_method('name')` in `src/pipeline/steps.py`. It implements
`map(self, t) -> YnabTransaction` (for `map` steps) and/or `filter(self, t) -> bool` (for
`filter` steps — return `True` to keep, `False` to drop). `__init__` receives the step's
YAML params as keyword arguments, plus `ctx` (the `PipelineContext`); accept `**kwargs` to
ignore the rest.

```python
@register_method('my_transform')
class MyTransform:
    def __init__(self, some_param: str, **kwargs):
        self.param = some_param

    def map(self, t: YnabTransaction) -> YnabTransaction:
        # modify t
        return t
```

Then use in pipeline YAML:

```yaml
- map:
    type: my_transform
    some_param: value
```

A step given as a bare string (`- map: my_transform`) is instantiated with no params.

### Custom transaction sources

Implement `YnabTransactionSource` in `src/sources/`:

```python
class MySource(YnabTransactionSource):
    def read(self) -> Iterable[YnabTransaction]:
        ...
```

Wire it into the read step builder in `src/pipeline/steps.py`. See `BankApiSource` for the pattern.
