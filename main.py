#!/usr/bin/env python3
"""
Sysmon - Script di avvio rapido.
Riconosce ed esegue automaticamente l'ambiente virtuale locale (.venv) se presente.
"""

from __future__ import annotations

import os
import sys
import subprocess

# Rilevamento automatico e transizione trasparente a .venv se non già attivo
def _ensure_virtualenv():
    project_dir = os.path.dirname(os.path.abspath(__file__))
    venv_win = os.path.join(project_dir, ".venv", "Scripts", "python.exe")
    venv_nix = os.path.join(project_dir, ".venv", "bin", "python")
    venv_py = venv_win if os.path.isfile(venv_win) else (venv_nix if os.path.isfile(venv_nix) else None)

    if venv_py:
        current_py = os.path.abspath(sys.executable).lower()
        target_py = os.path.abspath(venv_py).lower()
        if current_py != target_py:
            # Re-invoca se stesso usando l'interprete del virtualenv dove sono installate le librerie
            script_path = os.path.abspath(__file__)
            res = subprocess.run([venv_py, script_path] + sys.argv[1:], cwd=project_dir)
            sys.exit(res.returncode)

_ensure_virtualenv()

try:
    from sysmon.__main__ import main
except ModuleNotFoundError as e:
    missing_mod = getattr(e, "name", str(e))
    print(f"\n[ERRORE] Modulo mancante: {missing_mod}")
    print("Le dipendenze non risultano installate nell'ambiente Python corrente.")
    print("Per risolvere:")
    print("  1. Attiva il virtual environment:")
    print("       .\\.venv\\Scripts\\Activate.ps1    (PowerShell)")
    print("       .\\.venv\\Scripts\\activate.bat    (CMD)")
    print("  2. Oppure installa le dipendenze:")
    print("       pip install -r requirements.txt\n")
    sys.exit(1)

if __name__ == "__main__":
    main()
