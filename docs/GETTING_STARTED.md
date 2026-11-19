# Getting Started with Internet Health Monitor Development

**Choose your development environment and get coding in minutes**

---

## TL;DR (30 seconds)

### Option 1: Local Python (Fastest)
```bash
git clone <repo-url>
cd internet_health_monitor
make setup && make setup-current    # needs uv: creates .venv and .venv-current
code .                # Opens VS Code - that's it!
```

### Option 2: Dev Container (Zero Setup)
```bash
git clone <repo-url>
cd internet_health_monitor
code .                # Opens VS Code
# Press F1 → "Dev Containers: Reopen in Container"
# Wait 2-3 minutes for first-time build
```

---

## Quick Decision Tree

```
Do you have dependency or environment issues?
├─ YES → Use Dev Container (guaranteed consistency)
└─ NO  → Is speed critical for your workflow?
         ├─ YES → Use Local Python (fastest)
         └─ NO  → Use Dev Container (safer)
```

**Still unsure?** Start with Local Python - it's simpler and faster.

---

## Comparison

| Feature | Local Python | Dev Container |
|---------|--------------|---------------|
| **Setup Time** | ⚡ 2 min | ⏱️ 5 min (first time) |
| **Test Speed** | ⚡⚡⚡ Fastest | ⚡⚡ Fast |
| **Isolation** | ❌ Uses your system | ✅ Complete isolation |
| **Consistency** | ⚠️ Platform-dependent | ✅ Guaranteed |
| **Disk Space** | 📦 ~500MB | 📦 ~2GB |

---

## Option 1: Local Python Setup

### Prerequisites
- **[uv](https://docs.astral.sh/uv/)** (installs Python 3.14 for you)
- **Git**

### Steps

1. **Clone and setup:**
   ```bash
   git clone <repo-url>
   cd internet_health_monitor
   make setup && make setup-current
   ```

2. **Open in VS Code:**
   ```bash
   code .
   ```

3. **Verify:**
   ```bash
   pytest
   ```

---

## Option 2: Dev Container Setup

### Prerequisites
- **Docker Desktop** installed and running
- **VS Code** with "Dev Containers" extension

### Steps

1. **Clone:**
   ```bash
   git clone <repo-url>
   cd internet_health_monitor
   code .
   ```

2. **Reopen in container:**
   - VS Code will prompt "Reopen in Container" → Click it
   - **OR** Press `F1` → "Dev Containers: Reopen in Container"
   - Wait 2-5 minutes for first-time build

3. **Verify:**
   ```bash
   pytest
   ```

---

## VS Code Tasks

Press `Ctrl+Shift+P` → **"Tasks: Run Task"**:

| Task | Description |
|------|-------------|
| **Setup Local Python Environment** | Create .venv and install dependencies |
| **Run All Tests** | Full pytest suite |
| **Run Quick Tests** | Fast tests with early exit |
| **Lint Code** | Check code style with Ruff |
| **Format Code** | Auto-format with Black |
| **Quick Validation** | Lint + format check |

---

## Switching Environments

### From Local → Dev Container
1. Press `F1` → "Dev Containers: Reopen in Container"

### From Dev Container → Local
1. Press `F1` → "Dev Containers: Reopen Folder Locally"
2. Activate venv: `source .venv/bin/activate`

---

## Troubleshooting

### "Cannot find Python interpreter"
- **Local:** Run `make setup`, then `source .venv/bin/activate`
- **Container:** Press `F1` → "Dev Containers: Rebuild Container"

### "Tests not running"
```bash
# Check pytest is installed
pip list | grep pytest

# Reinstall dependencies
make setup && make setup-current
```

### "Docker container won't start"
1. Check Docker is running: `docker ps`
2. Restart Docker Desktop
3. Rebuild: `F1` → "Dev Containers: Rebuild Container"

---

## Quick Reference

| Task | Command |
|------|---------|
| Setup local | `make setup && make setup-current` |
| Activate venv | `source .venv/bin/activate` |
| Run tests | `pytest` |
| Format code | `black .` |
| Lint code | `ruff check .` |
| Open in container | `F1` → "Dev Containers: Reopen in Container" |

---

**You're all set!** 🚀
