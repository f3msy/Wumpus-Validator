import os
import random
import string
import threading
import time
from pathlib import Path

import requests
from rich.console import Console
from rich.panel import Panel

ENDPOINT = "https://discord.com/api/v9/users/@me/pomelo-attempt"
HITS = Path("hits.txt")
TOKENS = Path("tokens.txt")
WEBHOOK = "Put your own webhook URL in here"
THREADS, DELAY = 3, 0.1

LETTERS, DIGITS = string.ascii_lowercase, string.digits
# L = letters N = digits C = letters and digits
CHARSETS = {"L": LETTERS, "N": DIGITS, "C": LETTERS + DIGITS}


def generate(kind: str, length: int) -> str:
    while True:
        name = "".join(random.choices(CHARSETS[kind], k=length))
        if kind != "C" or (any(c in LETTERS for c in name) and any(c in DIGITS for c in name)):
            return name


def space_size(kind: str, length: int) -> int:
    if kind == "C":
        return 36 ** length - 26 ** length - 10 ** length
    return len(CHARSETS[kind]) ** length


CUSTOM = "8"
MODES = {"1": ("4C", "C", 4), "2": ("4L", "L", 4), "3": ("4N", "N", 4),
         "4": ("3L", "L", 3), "5": ("3C", "C", 3), "6": ("3N", "N", 3),
         "7": ("5C", "C", 5)}

console = Console()
stop = threading.Event()


def load_tokens() -> list[str]:
    raw = os.getenv("DISCORD_TOKENS", "")
    if not raw and TOKENS.exists():
        raw = TOKENS.read_text(encoding="utf-8")
    return list(dict.fromkeys(t.strip() for t in raw.replace(",", "\n").splitlines() if t.strip()))


class TokenPool:
    def __init__(self, tokens: list[str]):
        self.tokens, self.cooldown, self.lock = list(tokens), {}, threading.Lock()

    def get(self) -> str | None:
        while not stop.is_set():
            with self.lock:
                if not self.tokens:
                    return None
                now = time.time()
                ready = [t for t in self.tokens if self.cooldown.get(t, 0) <= now]
                if ready:
                    return random.choice(ready)
            time.sleep(0.5)
        return None

    def rate_limit(self, token: str, seconds: float) -> None:
        with self.lock:
            self.cooldown[token] = time.time() + seconds

    def remove(self, token: str) -> int:
        with self.lock:
            if token in self.tokens:
                self.tokens.remove(token)
            return len(self.tokens)


class Stats:
    def __init__(self):
        self.lock, self.checked, self.hits, self.seen = threading.Lock(), 0, 0, set()

    def claim(self, name: str) -> bool:
        with self.lock:
            if name in self.seen:
                return False
            self.seen.add(name)
            return True

    def add(self, hit: bool) -> int:
        with self.lock:
            self.checked += 1
            self.hits += hit
            return self.hits


def notify(username: str) -> None:
    with open(HITS, "a", encoding="utf-8") as f:
        f.write(username + "\n")
    if WEBHOOK.startswith("https://"):
        try:
            requests.post(WEBHOOK, json={"content": f"**[HIT]** `{username}` is available."}, timeout=5)
        except requests.RequestException:
            pass


def check(username: str, pool: TokenPool, stats: Stats, session: requests.Session) -> None:
    token = pool.get()
    if token is None:
        console.print("[red]No valid tokens left - stopping.[/red]")
        stop.set()
        return

    try:
        r = session.post(ENDPOINT, headers={"Authorization": token}, json={"username": username}, timeout=10)
    except requests.RequestException as e:
        console.print(f"[red]Network error: {e}[/red]")
        time.sleep(2)
        return

    try:
        data = r.json()
    except ValueError:
        data = {}

    if r.status_code == 429:
        wait = float(data.get("retry_after", 5)) + 1
        pool.rate_limit(token, wait)
        console.print(f"[yellow]Rate limited ({wait:.0f}s) for token ...{token[-4:]}[/yellow]")
    elif r.status_code in (401, 403):
        left = pool.remove(token)
        console.print(f"[red]Token ...{token[-4:]} invalid and removed ({left} left)[/red]")
    elif r.status_code == 400:
        stats.add(False)
        console.print(f"[red]Invalid: {username}[/red]")
    elif r.status_code == 200:
        hit = data.get("taken") is False
        n = stats.add(hit)
        if hit:
            console.print(f"[green]Available: [bold]{username}[/bold] (hits: {n})[/green]")
            notify(username)
        else:
            console.print(f"[blue]Taken: {username}[/blue]")
    else:
        console.print(f"[red]Unexpected response {r.status_code}[/red]")


def worker(pool: TokenPool, stats: Stats, kind: str, length: int) -> None:
    session = requests.Session()
    space = space_size(kind, length)
    while not stop.is_set():
        if len(stats.seen) >= space:  # every possible name has been tried (this won't happen but just in case for small modes like 3N)
            stop.set()
            break
        name = generate(kind, length)
        if stats.claim(name):
            check(name, pool, stats, session)
            time.sleep(DELAY)


def run_mode(choice: str, pool: TokenPool) -> None:
    stats, session = Stats(), requests.Session()
    stop.clear()
    if choice == CUSTOM:
        name = console.input("[magenta]Username: [/magenta]").strip().lower()
        if 2 <= len(name) <= 32:
            check(name, pool, stats, session)
        else:
            console.print("[red]Username must be 2-32 characters long.[/red]")
        return

    _, kind, length = MODES[choice]
    threads = [threading.Thread(target=worker, args=(pool, stats, kind, length), daemon=True)
               for _ in range(THREADS)]
    for t in threads:
        t.start()
    try:
        while not stop.is_set() and any(t.is_alive() for t in threads):
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    stop.set()
    for t in threads:
        t.join(timeout=3)
    console.print(f"\n[cyan]Checked: {stats.checked} | Hits: [green]{stats.hits}[/green][/cyan]")


def main() -> None:
    tokens = load_tokens()
    if not tokens:
        console.print("[red]No tokens found. Create tokens.txt (one token per line).[/red]")
        return
    pool = TokenPool(tokens)

    menu = "\n".join(f"[cyan]{k}[/cyan] | {v[0]}" for k, v in MODES.items())
    menu += f"\n[cyan]{CUSTOM}[/cyan] | Check a specific username"
    while True:
        console.clear()
        console.print(Panel(menu, title="[bold]Wumpus Validator[/bold]", border_style="cyan", expand=False))
        choice = console.input("[magenta]Select mode (q = quit): [/magenta]").strip().lower()
        if choice == "q":
            break
        if choice not in MODES and choice != CUSTOM:
            console.print("[red]Invalid choice![/red]")
        else:
            run_mode(choice, pool)
        if not pool.tokens:
            console.print("[red]All tokens invalid - exiting.[/red]")
            break
        console.input("\nPress Enter to continue...")


if __name__ == "__main__":
    main()
