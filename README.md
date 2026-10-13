# Wumpus Validator

A lightweight Discord username availability checker.

## Setup

1. Install dependencies:

```bash
pip install requests rich
```

2. Add your tokens to `tokens.txt`, one per line (or set `DISCORD_TOKENS`, comma-separated).

3. Optional: set your webhook URL in `user.py` (the `WEBHOOK` constant at the top).

## Usage

```bash
python user.py
```

## Modes

| Mode | Pattern | Characters                              |
| :--: | :-----: | --------------------------------------- |
| 1    | 4C      | Letters and digits (4)                  |
| 2    | 4L      | Letters only (4)                        |
| 3    | 4N      | Digits only (4)                         |
| 4    | 3L      | Letters only (3)                        |
| 5    | 3C      | Letters and digits (3)                  |
| 6    | 3N      | Digits only (3)                         |
| 7    | 5C      | Letters and digits (5)                  |
| 8    | Custom  | Check a specific username               |

Hit rates depend on how many names are already taken and change over time.

## Output

Available usernames are saved to `hits.txt` and sent to the webhook if one is set.

## Configuration

Constants at the top of `user.py`:

| Constant  | Default | Description                    |
| --------- | :-----: | ------------------------------ |
| `WEBHOOK` | -       | Webhook URL for hit messages   |
| `THREADS` | `3`     | Number of worker threads       |
| `DELAY`   | `0.1`   | Pause between checks (seconds) |

## Tokens and speed

- More tokens means more checks per minute, because the script switches to another token while one is rate limited. It does not change the hit rate per check.
- Speed is also capped by `THREADS` and `DELAY`. If you add many tokens, raise `THREADS` gradually.
- If rate-limit messages (yellow) appear constantly, you have reached the limit and more tokens or threads will not help. Discord may also limit by IP, which all tokens share.

## Notes

- Tokens that return 401/403 are removed automatically. Rate-limited tokens cool down and are reused.
- A run stops once every possible name for the selected mode has been tried.
- Press `Ctrl+C` to stop a run, `q` in the menu to quit.
- Automating user accounts violates Discord's Terms of Service and can lead to bans. Keep `tokens.txt` and your webhook URL private.