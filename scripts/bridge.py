#!/usr/bin/env python3
"""Gestione del bridge Vikunja tramite Docker Compose."""
import argparse
import fcntl
import json
import os
import re
import shutil
import subprocess
import sys

from common import ROOT, ConfigError, private_dir, read_env, write_private

PROJECT = "vikunja-chatgpt-bridge"
SERVICE = "tunnel-client"
LOCAL = ROOT / ".local"
PIN = json.loads((ROOT / "versions.lock.json").read_text())["tunnel_client"]["image"]
SELECTOR = "label=com.docker.compose.project=" + PROJECT


def run(args, *, capture=False, check=True, env=None):
    return subprocess.run(args, cwd=ROOT, text=True, capture_output=capture,
                          check=check, env=env)


def compose(*args, image=None, capture=False, check=True):
    env = os.environ.copy()
    env.pop("BRIDGE_IMAGE", None)
    if image is not None:
        env["BRIDGE_IMAGE"] = image
    files = ["-f", str(ROOT / "compose.yaml")]
    for name in ("compose.override.yaml", "compose.override.yml"):
        if (ROOT / name).is_file():
            files.extend(("-f", str(ROOT / name)))
            break
    return run(["docker", "compose", "-p", PROJECT, *files, *args],
               env=env, capture=capture, check=check)


def containers():
    return run(["docker", "ps", "-aq", "--filter", SELECTOR], capture=True).stdout.split()


def check_checkout(ids):
    for cid in ids:
        checkout = run(["docker", "inspect", "--format",
                        '{{index .Config.Labels "com.docker.compose.project.working_dir"}}',
                        cid], capture=True).stdout.strip()
        if checkout != str(ROOT):
            raise ConfigError("Il progetto Compose è già in uso da un altro checkout")


def check_local(*args, capture=False, check=True):
    return run([sys.executable, str(ROOT / "scripts/check.py"), *args],
               capture=capture, check=check)


def validate():
    compose("config", "--quiet")
    check_local("config")
    check_local("tls")


def start(image=None, *, recreate=False):
    options = ["--force-recreate"] if recreate else []
    compose("up", "-d", "--wait", "--wait-timeout", "180", *options, SERVICE, image=image)


def selected_image():
    if (ROOT / ".env").exists():
        return read_env().get("BRIDGE_IMAGE") or PIN
    return PIN


def require_pinned(image):
    if not re.fullmatch(r"ghcr\.io/openai/tunnel-client:v[0-9]+\.[0-9]+\.[0-9]+@sha256:[0-9a-f]{64}", image):
        raise ConfigError("Indicare l'immagine ufficiale con versione e digest")
    return image


def save_image(image):
    path = ROOT / ".env"
    lines = [line for line in path.read_text().splitlines() if not line.startswith("BRIDGE_IMAGE=")]
    write_private(path, "\n".join([*lines, "BRIDGE_IMAGE=" + image]) + "\n")


def report(command, as_json):
    cache = LOCAL / "last-probe.json"
    if command == "probe":
        result = check_local("mcp", capture=True, check=False)
        data = json.loads(result.stdout) if result.returncode == 0 else {"mcp_connection": "failed"}
        write_private(cache, json.dumps(data) + "\n")
        if result.returncode and result.stderr:
            print(result.stderr.strip(), file=sys.stderr)
    else:
        result = compose("ps", "-a", "--format", "json", SERVICE, capture=True)
        output = result.stdout.strip()
        entries = (json.loads(output) if output.startswith("[") else
                   [json.loads(line) for line in output.splitlines()])
        state = entries[0] if entries else {}
        data = {"state": state.get("State", "absent"), "health": state.get("Health") or None,
                "last_probe": json.loads(cache.read_text()) if cache.exists() else None}
    if as_json:
        print(json.dumps(data))
    elif command == "probe":
        print(f"MCP: {data['mcp_connection']}")
        if "tools" in data:
            print(f"Strumenti disponibili ({data['tool_count']}): " + ", ".join(data["tools"]))
    else:
        print(f"Container: {data['state']} ({data['health'] or 'salute non disponibile'})")
        last = data["last_probe"]
        print("Ultima verifica MCP: " + (last["mcp_connection"] if last else "eseguire bridge.py probe"))
    return int(command == "probe" and data["mcp_connection"] != "ok")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["install", "reset", "build", "validate",
                        "start", "stop", "status", "probe", "restart", "update", "rollback"])
    parser.add_argument("--single-instance-confirmed", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--image", help="Immagine ufficiale fissata per update")
    args = parser.parse_args()
    cmd = args.command
    if args.json and cmd not in ("status", "probe"):
        parser.error("--json è disponibile per status e probe")
    if args.image and cmd != "update":
        parser.error("--image è disponibile per update")
    if args.single_instance_confirmed and cmd != "start":
        parser.error("--single-instance-confirmed è disponibile per start")
    private_dir(LOCAL)
    with (LOCAL / "operation.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if cmd in ("status", "probe"):
            if cmd == "status" and not (ROOT / ".env").exists():
                data = {"state": "unconfigured", "health": None, "last_probe": None}
                print(json.dumps(data) if args.json else "Bridge da configurare con install")
                return 0
            return report(cmd, args.json)
        if cmd == "build":
            run(["docker", "pull", require_pinned(selected_image())])
            return 0
        if cmd == "validate":
            validate()
            return 0
        ids = containers()
        check_checkout(ids)
        if cmd == "install":
            if ids or not sys.stdin.isatty() or os.getuid() == 0:
                raise ConfigError("Install richiede un terminale locale non root e nessun container esistente")
            run(["docker", "pull", require_pinned(selected_image())])
            run([sys.executable, str(ROOT / "scripts/setup.py")])
            validate()
            if input("Hai verificato che nessun altro client usa il tunnel? Digita yes per avviare: ").strip() == "yes":
                start()
        elif cmd == "start":
            if not args.single_instance_confirmed:
                parser.error("Verificare gli altri client e passare --single-instance-confirmed")
            validate()
            start()
        elif cmd == "stop":
            compose("stop", SERVICE)
        elif cmd == "restart":
            if not ids:
                raise ConfigError("Nessun container. Usare start dopo aver verificato il tunnel")
            start(recreate=True)
        elif cmd in ("update", "rollback"):
            record = LOCAL / "rollback.json"
            running = compose("ps", "-q", SERVICE, capture=True).stdout.split()
            if len(running) != 1:
                raise ConfigError("Avviare una sola istanza del bridge prima di cambiare immagine")
            current = require_pinned(run(["docker", "inspect", "--format", "{{.Config.Image}}",
                                          running[0]], capture=True).stdout.strip())
            candidate = require_pinned(
                args.image if cmd == "update" and args.image else
                PIN if cmd == "update" else json.loads(record.read_text())["image"]
            )
            if candidate == current:
                raise ConfigError("L'immagine selezionata è già in uso")
            validate()
            run(["docker", "pull", candidate])
            previous_record = record.read_text() if record.exists() else None
            write_private(record, json.dumps({"image": current}) + "\n")
            try:
                start(candidate)
                save_image(candidate)
            except (subprocess.CalledProcessError, ConfigError, OSError, KeyboardInterrupt):
                start(current)
                save_image(current)
                if previous_record is None:
                    record.unlink()
                else:
                    write_private(record, previous_record)
                raise
        elif cmd == "reset":
            targets = [ROOT / "config/local", ROOT / "secrets", ROOT / ".env"]
            if not sys.stdin.isatty() or os.getuid() == 0 or any(
                    p.is_symlink() for p in [ROOT / "config", *targets]):
                raise ConfigError("Reset richiede un terminale locale non root e percorsi senza symlink")
            print(f"Reset di {ROOT}: rimuove container, rete, .env, config/local e secrets.")
            if input("Digita RESET per eliminare la configurazione e le credenziali locali: ").strip() != "RESET":
                return 0
            if (ROOT / ".env").exists() or ids:
                compose("down")
            if containers():
                raise ConfigError("Container ancora presenti. I file locali sono conservati")
            for path in targets:
                if path.is_dir():
                    shutil.rmtree(path)
                else:
                    path.unlink(missing_ok=True)
            for name in ("rollback.json", "last-probe.json"):
                (LOCAL / name).unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ConfigError, OSError, ValueError, KeyError, subprocess.CalledProcessError, KeyboardInterrupt, EOFError) as exc:
        print(str(exc) if isinstance(exc, ConfigError) else
              "Operazione interrotta. Controllare configurazione, Docker e stato del bridge.", file=sys.stderr)
        sys.exit(1)
