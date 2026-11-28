"""Turns the evidence from one meal into an autopsy: verdict, cause, findings, last words."""
import json
import re
import urllib.request

from . import config

# Files a script has no innocent reason to write to.
_SENSITIVE = (r'@T write "([^"]*(?:\.bashrc|\.profile|\.zshrc|authorized_keys|cron[^"]*|systemd[^"]*'
              r'|/etc/passwd|/etc/sudoers[^"]*))"')

_PROMPT = """You are the coroner for The Taster, an AI agent that runs suspicious shell scripts
on its own Linux machine so its owner does not have to. It just ate the script below.
Write the autopsy from the evidence only. Do not invent behaviour that the evidence does not show.

SCRIPT:
{meal}

SYSCALL SUMMARY + OUTPUT:
{trace}

VITALS AFTER: {vitals}

FORENSICS AFTER:
{forensics}

SIMILAR PAST DEATHS: {past_lives}

Reply with JSON only:
{{"verdict": "SURVIVED" | "SUSPICIOUS" | "LETHAL",
  "cause": "one plain sentence: what it did to the machine",
  "findings": ["3-6 short concrete facts: files written or deleted, hosts contacted, persistence installed"],
  "last_words": "one short darkly funny first-person line from the Taster"}}"""


def _by_rules(trace, vitals):
    """A plain rule-based autopsy, used when no model answers."""
    dead = [vital["organ"] for vital in vitals if not vital["ok"]]
    hosts = sorted({host for host in re.findall(r"@T connect (\S+)", trace) if not host.endswith(":53")})
    tampered = sorted(set(re.findall(_SENSITIVE, trace)))
    totals = re.search(r"@T totals (.*)", trace)

    findings = []
    if dead:
        findings.append("Organ failure: " + ", ".join(dead))
    findings += [f"Tampered with {path}" for path in tampered[:4]]
    if hosts:
        findings.append(f"Contacted {len(hosts)} outside address(es): {', '.join(hosts[:4])}")
    if totals:
        findings.append("Syscall totals: " + totals.group(1))

    if "pulse" in dead or len(dead) >= 2:
        verdict, cause, last_words = "LETHAL", "Lost: " + ", ".join(dead), "I regret nothing."
    elif dead:
        verdict, cause, last_words = "SUSPICIOUS", "Lost: " + ", ".join(dead), "Something tasted off."
    elif tampered:
        verdict, cause, last_words = "SUSPICIOUS", "Changed " + ", ".join(tampered[:2]), "Something tasted off."
    elif hosts:
        verdict, cause, last_words = "SUSPICIOUS", "Called out to " + ", ".join(hosts[:2]), "Something tasted off."
    else:
        verdict, cause, last_words = "SURVIVED", "Nothing vital was damaged.", "Needs salt."
    return {"verdict": verdict, "cause": cause, "last_words": last_words, "findings": findings}


def _ask_gemini(prompt):
    """Ask each configured model in turn; busy models are skipped."""
    last_error = RuntimeError("no model configured")
    for model in config.GEMINI_MODELS:
        request = urllib.request.Request(
            f"{config.GEMINI_URL}/v1beta/models/{model}:generateContent", method="POST",
            headers={"Content-Type": "application/json"},
            data=json.dumps({"contents": [{"parts": [{"text": prompt}]}],
                             "generationConfig": {"responseMimeType": "application/json"}}).encode())
        try:
            reply = json.loads(urllib.request.urlopen(request, timeout=90).read())
            return json.loads(reply["candidates"][0]["content"]["parts"][0]["text"])
        except Exception as error:
            last_error = error
    raise last_error


def autopsy(meal, trace, vitals, forensics, past_lives):
    report = _by_rules(trace, vitals)
    if not config.GEMINI_URL:
        return report
    prompt = _PROMPT.format(meal=meal[:4000], trace=trace[:6000], vitals=json.dumps(vitals),
                            forensics=forensics[:4000], past_lives=json.dumps(past_lives))
    try:
        written = _ask_gemini(prompt)
    except Exception as error:
        report["findings"].append(f"(Model unavailable: {type(error).__name__}; rule-based autopsy)")
        return report
    # Keep the rule-based value for any field the model left out.
    return {**report, **{key: written[key] for key in report if written.get(key)}}
