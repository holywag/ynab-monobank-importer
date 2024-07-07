# YNAB transaction importer for Ukrainian banks

## Supported banks

|||
|-|-|
|Monobank|Using [wrapper](https://github.com/holywag/mono-api.git) for [public monobank API](https://api.monobank.ua/docs/index.html)|
|ABank|Parsing PDFs|
|PUMB|Parsing PDFs|
|PrivatBank|Parsing PDFs|
|Sense|Parsing CSVs|

## Dependencies

Python 3.11.6

```
git submodule update -f --recursive --init
pip install $(ls -d api/*) -r ./requirements.txt
```

## Configuration

Set up configuration at the corresponding json files at `config` directory.

## Run

```
python src/main.py
```
