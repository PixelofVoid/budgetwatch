# BudgetWatch

Local, offline household cash-flow tracker for Linux. Log paychecks and bills, see leftover this month and the next six. No bank logins, cloud, or network. AppImage or run from source.

## Features

- Dashboard: this-month cash flow, leftover after entered bills, category spend, 6-month leftover chart
- Plan: planned vs actual by category
- Income: numbered pay sources, paycheck logging
- Recurring bills, cash flow, transactions
- Dark theme, CSV export
- Data stays in `~/.local/share/budgetwatch/budgetwatch.db`

No bank APIs, accounts, ads, or network calls.

## Install (Linux)

### AppImage (any distro)

Download **[BudgetWatch-1.0.0-x86_64.AppImage](https://github.com/PixelofVoid/budgetwatch/releases/download/v1.0.0/BudgetWatch-1.0.0-x86_64.AppImage)** from [Releases](https://github.com/PixelofVoid/budgetwatch/releases/latest):

```bash
chmod +x BudgetWatch-1.0.0-x86_64.AppImage
./BudgetWatch-1.0.0-x86_64.AppImage
```

If the AppImage cannot mount (`libfuse.so.2` missing), install FUSE 2 or run with `--appimage-extract-and-run`.

To build the AppImage yourself:

```bash
bash packaging/build-appimage.sh
bash packaging/install-linux.sh
```

### From source

Python 3.12+ and PySide6:

```bash
git clone https://github.com/PixelofVoid/budgetwatch.git
cd budgetwatch
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
PYTHONPATH=src python -m budgetwatch
```

## Android

Not supported. This is a Linux desktop Qt app.

## Tests

```bash
source .venv/bin/activate
PYTHONPATH=src pytest
```

## License

MIT. See [LICENSE](LICENSE).
