# finish-protocol-generator

Tool for generating finish protocols for offline referee events.

## Setup

### 1. Download the project

Install Git if you don't have it:

- **macOS:** `brew install git`
- **Linux (Ubuntu / Debian):** `sudo apt install git`
- **Windows:** download from [git-scm.com](https://git-scm.com/downloads) and run the installer

Then clone the repository:

```bash
git clone https://github.com/dchernykh1984/FinishProtocolGeneratorPython.git
cd FinishProtocolGeneratorPython
```

All subsequent commands should be run from the `FinishProtocolGeneratorPython` folder.

### 2. Install Python 3.14

This project requires **Python 3.14**. Installing a different version will result in an error when running `poetry install`.

**macOS**

```bash
brew install python@3.14
```

If you don't have Homebrew yet, install it first from [brew.sh](https://brew.sh).

**Linux (Ubuntu / Debian)**

The system `python3` package is usually not 3.14. Install it via the deadsnakes PPA:

```bash
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt update
sudo apt install python3.14 python3.14-venv
```

**Windows**

Download the **Python 3.14** installer from [python.org/downloads](https://www.python.org/downloads/) and run it. On the first screen, check **"Add Python to PATH"** before clicking Install.

Verify the installation in a terminal:

- **macOS / Linux:** `python3.14 --version`
- **Windows:** `py -3.14 --version`

The output should start with `Python 3.14`.

### 3. Install Poetry

**macOS**

```bash
brew install pipx
pipx ensurepath
pipx install poetry
```

**Linux (Ubuntu / Debian)**

```bash
pip3 install pipx
pipx ensurepath
pipx install poetry
```

Restart your terminal after running `pipx ensurepath`.

**Windows**

Open **Command Prompt** or **PowerShell** and run:

```powershell
pip install pipx
pipx ensurepath
pipx install poetry
```

Restart your terminal after running `pipx ensurepath`.

### 4. Create virtual environment and install dependencies

```bash
poetry config virtualenvs.in-project true
poetry install --no-root
```

### 5. Set up pre-commit hooks

```bash
poetry run pre-commit install
poetry run pre-commit install --hook-type commit-msg
```

After that pre-commit hooks will run automatically on every commit.

To run all checks manually across all files:

```bash
poetry run pre-commit run --all-files
```

## Running the application

```bash
poetry run python -m app.main
```

> **Note:** use `-m app.main`, not `python app/main.py`. The `-m` flag adds the
> project root to `sys.path` so that the `app` package is importable.

## Cycling-site integration

The application can upload finish protocols directly to the cycling-site API.

1. Open **Settings -> HTTP** in the application.
2. Enter the site URL (e.g. `https://cycling.codered.cloud`).
3. Enter the upload token - find it on the competition detail page when logged
   in as an organizer or admin.

After generating a protocol, the **Upload** button sends it to
`POST /api/v1/protocols/upload/` as a multipart HTML file with the competition
token. The site stores the protocol and makes it visible on the competition page.

## Contributing

Before requesting a review, make sure the CI pipeline passes on your pull request. Once the pipeline is green, request a review from [@dchernykh1984](https://github.com/dchernykh1984).
