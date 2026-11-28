# The Taster

Kings had someone eat the meal first. The Taster is a personal agent that runs
your suspicious shell scripts on its own computer, dies if it has to, gets
restored from a checkpoint a few seconds later, and tells you what killed it.

Built for [Fly.io Hacksgiving 2026](https://fly.io/hacksgiving/) on
[Sprites](https://fly.io/sprites).

Live graveyard: https://butler-b624l.sprites.app

## What it does

Paste a command, a script, or a URL to an install script. Then:

1. **It remembers.** The meal is embedded and compared against every earlier
   death in Pinecone. If it looks familiar: "I have died like this before."
2. **It eats.** The script really runs, as root, on the `taster` Sprite, under
   `strace`. A summariser condenses the syscalls into programs run, files
   written and deleted, and hosts contacted.
3. **It gets a check-up.** Six vitals (can it run a command, coreutils, Python,
   home directory, `/etc` and `/usr`, DNS config) plus forensics: new files,
   cron, shell rc files, ssh keys, listening ports.
4. **It is resurrected.** The Butler restores the Taster's clean checkpoint.
   Usually a few seconds, including after `rm -rf /`.
5. **It gets an autopsy.** Gemini reads the evidence and writes the verdict
   (SURVIVED, SUSPICIOUS or LETHAL), the cause, the findings and the Taster's
   last words. The tombstone goes on the public graveyard page.

## How it is built

```
you ── owner key ──▶ butler Sprite ── Sprites API ──▶ taster Sprite
                      butler/                          runs the meal under strace
                      graveyard page                   restored from checkpoint v2
                        │
                        ├─ Pinecone connector: embed + store + recall past deaths
                        └─ Gemini connector:   write the autopsy
```

Two Sprites, on purpose. The Taster runs untrusted code, so it has access to no
connectors at all. The Butler never runs the meal; it only watches.

```
butler/              runs on the butler Sprite
  config.py          settings from the environment or butler.env
  sprites.py         Sprites API client: run a command on the Taster, restore it
  tasting.py         the pipeline: recall, serve, eat, vitals, resurrect, autopsy
  coroner.py         rule-based autopsy, then Gemini writes the final one
  memory.py          Pinecone: embed, store and recall past deaths
  store.py           SQLite graveyard
  server.py          HTTP API and the page
  static/index.html  the graveyard page
taster/summ.awk      runs on the taster Sprite; condenses strace output
butler.env.example   settings template
```

Python standard library only, so there is nothing to install on the Sprite.
`summ.awk` is already in memory when the meal starts, so it survives `rm -rf /`.

### Sprites features used

- **Checkpoint and restore**: the whole trick. Death is cheap because rebirth takes seconds.
- **Connectors**: Pinecone (memory) and Google Gemini (coroner), both restricted
  to Sprites whose name starts with `butler`. No provider key is on either box.
- **Sprite URLs and services**: the Butler is a service on port 8080 that wakes on request.
- **Hardware isolation**: the reason it is fine to run `rm -rf /` as root.

## Run your own

```bash
sprite create --skip-console taster
sprite create --skip-console butler

# Taster: tracing tools, then a clean checkpoint to resurrect from
sprite exec -s taster -- bash -c 'sudo apt-get install -y strace && sudo mkdir -p /opt/taster /var/tmp/taste && sudo chown sprite /opt/taster /var/tmp/taste'
sprite exec --stdin -s taster -- bash -c 'cat > /opt/taster/summ.awk' < taster/summ.awk
sprite checkpoint create -s taster --comment clean      # note the id, e.g. v2

# Butler: code, settings, service
tar czf - butler | sprite exec --stdin -s butler -- bash -c 'mkdir -p ~/taster && cd ~/taster && tar xzf -'
# copy butler.env.example to ~/taster/butler.env on the butler Sprite and fill it in
sprite exec -s butler -- sprite-env services create butler --cmd /.sprite/bin/python3 \
  --args "-m,butler" --dir /home/sprite/taster --http-port 8080
sprite config update -s butler --url-auth public
```

Add the Pinecone and Gemini connectors in the Fly dashboard (Sprites →
Connectors) with name prefix `butler`, create a 1024-dimension cosine index named
`taster-past-lives` in Pinecone, and put both gateway URLs in `butler.env`.

## Honest limits

- The Butler holds a Sprites API token in `butler.env`. A connector cannot front
  the Sprites API itself (the gateway refuses it), so this one secret is on the box.
- The Taster's outbound network is open, so it can show which hosts a script
  calls. Only the holder of the owner key can feed it, and meals are cut off at 45 seconds.
- It reports what a script did in one run on one Ubuntu machine. A script that
  behaves differently elsewhere, or waits longer than 45 seconds, will fool it.
- Do not feed it real malware. It is for install scripts and "what does this command do".
