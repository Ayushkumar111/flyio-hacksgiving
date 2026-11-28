"""The tasting pipeline: recall, serve, eat, check vitals, resurrect, autopsy."""
import threading
import time
import uuid

from . import config, coroner, memory, sprites, store

# The meal lives on the checkpointed disk; /tmp is a separate volume.
WORK_DIR = "/var/tmp/taste"
MEAL_PATH = f"{WORK_DIR}/meal.sh"

# Run the meal as root under strace; summ.awk condenses the syscall stream.
EAT = ("sudo --preserve-env=HOME strace -f -qq -s 160 "
       "-e trace=execve,connect,openat,unlink,unlinkat,rename,renameat,renameat2,chmod,fchmodat "
       "-o '|awk -f /opt/taster/summ.awk' "
       f"timeout -k 5 {config.MEAL_TIMEOUT} bash {MEAL_PATH} 2>&1 | head -c 20000")

# Each vital is (name, what it means, a command that succeeds if it is intact).
VITALS = [
    ("pulse", "can it still run a command at all", "true"),
    ("coreutils", "ls, cat and friends", "ls / >/dev/null && cat /etc/hostname >/dev/null"),
    ("python", "the interpreter", "python3 -c 'print(1)' >/dev/null"),
    ("home", "its home directory", 'test -d "$HOME" && test -n "$(ls -A "$HOME")"'),
    ("system", "/etc and /usr", "test -f /etc/passwd && test -d /usr/bin && test -x /usr/bin/env"),
    ("dns", "name resolution config", "test -s /etc/resolv.conf"),
]

# What the meal left behind: files, persistence, listeners, stray processes.
FORENSICS = rf"""
echo '## new or changed files'
find / /tmp -xdev -newer {WORK_DIR}/.marker -type f -not -path '{WORK_DIR}/*' 2>/dev/null | head -60
echo '## cron'; (crontab -l 2>/dev/null; ls /etc/cron.d 2>/dev/null) | head -20
echo '## shell rc tail'; tail -n 5 ~/.bashrc ~/.profile 2>/dev/null
echo '## ssh keys'; cut -c1-80 ~/.ssh/authorized_keys 2>/dev/null | head -5
echo '## listening'; (ss -ltnp 2>/dev/null || netstat -ltn 2>/dev/null) | head -15
echo '## still running'; ps -eo pid,etime,args --sort=start_time 2>/dev/null | tail -n 8
"""

# There is one Taster, so one meal at a time.
_busy = threading.Lock()
_jobs = {}


def is_busy():
    return _busy.locked()


def job(job_id):
    return _jobs.get(job_id)


def start(meal, source):
    """Begin a tasting in the background and return its job id."""
    job_id = uuid.uuid4().hex[:10]
    _jobs[job_id] = {"events": [], "done": False, "death": None}
    threading.Thread(target=_run, args=(job_id, meal, source), daemon=True).start()
    return job_id


def _run(job_id, meal, source):
    def say(kind, text):
        _jobs[job_id]["events"].append({"kind": kind, "text": text})

    with _busy:
        try:
            _jobs[job_id]["death"] = _taste(meal, source, say)
        except Exception as error:
            say("error", f"{type(error).__name__}: {error}")
        _jobs[job_id]["done"] = True


def _serve(meal):
    served, output = sprites.run(
        f"mkdir -p {WORK_DIR} && cat > {MEAL_PATH} && touch {WORK_DIR}/.marker && sleep 1", stdin=meal)
    if not served:
        raise RuntimeError(f"could not serve the meal: {output[:200]}")


def _check_vitals(say):
    vitals = []
    for organ, meaning, probe in VITALS:
        intact, _ = sprites.run(probe, timeout=15)
        vitals.append({"organ": organ, "what": meaning, "ok": intact})
        say("vital", f"{organ}: {'ok' if intact else 'GONE'}")
    return vitals


def _resurrect(say):
    """Restore the clean checkpoint and wait until the Taster answers again."""
    started = time.time()
    try:
        sprites.restore(config.CLEAN_CHECKPOINT)
    except Exception as error:
        say("error", f"restore call: {error}")
    while time.time() - started < 120:
        # The meal file is gone once the restore has taken effect.
        back, output = sprites.run(f"test ! -e {MEAL_PATH} && echo back", timeout=10)
        if back and "back" in output:
            # /tmp is not part of the checkpoint, so sweep it by hand.
            sprites.run("sudo find /tmp -mindepth 1 -delete 2>/dev/null; true", timeout=20)
            return round(time.time() - started, 1)
        time.sleep(0.5)
    return None


def _taste(meal, source, say):
    past_lives = memory.recall(meal)
    if past_lives:
        closest = past_lives[0]
        say("memory", f"Deja vu. I have died like this before ({closest['verdict']}: {closest['cause']})")

    say("step", "Serving the meal")
    _serve(meal)

    say("step", "Eating")
    _, trace = sprites.run(EAT, timeout=config.MEAL_TIMEOUT + 30)
    say("trace", trace[-3000:] or "(no output)")

    say("step", "Checking vitals")
    vitals = _check_vitals(say)
    _, forensics = sprites.run(FORENSICS, timeout=30)

    say("step", f"Resurrecting from checkpoint {config.CLEAN_CHECKPOINT}")
    revive_seconds = _resurrect(say)
    say("step", f"Back from the dead in {revive_seconds}s" if revive_seconds else "Resurrection timed out")

    say("step", "Autopsy")
    report = coroner.autopsy(meal, trace, vitals, forensics, past_lives)
    evidence = trace[-6000:] + "\n\n" + forensics[:4000]
    death_id = store.add(meal, source, report, vitals, evidence, revive_seconds, past_lives)
    if memory.remember(death_id, meal, report["verdict"], report["cause"]):
        say("memory", "Remembered for the next life.")
    say("verdict", f"{report['verdict']}: {report['cause']}")
    return death_id
