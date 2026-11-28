"""Thin client for the Sprites API calls the Butler makes on the Taster."""
import json
import re
import urllib.parse
import urllib.request

from . import config


def _request(method, path, query=None, body=None, timeout=120):
    url = f"{config.SPRITES_API}/v1/sprites/{config.TASTER}{path}"
    if query:
        url += "?" + urllib.parse.urlencode(query, quote_via=urllib.parse.quote)
    headers = {"Authorization": f"Bearer {config.SPRITES_TOKEN}"}
    if body is not None:
        headers["Content-Type"] = "application/octet-stream"
    request = urllib.request.Request(url, data=body, method=method, headers=headers)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def run(script, stdin=None, timeout=60):
    """Run a bash script on the Taster. Returns (succeeded, output)."""
    query = [("cmd", "bash"), ("cmd", "-c"), ("cmd", script + '\necho "@EXIT:$?"')]
    if stdin is not None:
        query.append(("stdin", "true"))
    try:
        raw = _request("POST", "/exec", query, stdin.encode() if stdin is not None else None, timeout)
    except Exception as error:
        # A dead machine, a timeout and a 5xx all mean the same thing: no pulse.
        return False, f"{type(error).__name__}: {error}"
    # The stream tags chunks: \x01 stdout, \x02 stderr, \x03 plus an exit byte.
    raw = re.sub(rb"\x03.?\Z", b"", raw, flags=re.S).replace(b"\x01", b"").replace(b"\x02", b"")
    text = raw.decode("utf-8", "replace")
    exit_code = re.search(r"@EXIT:(\d+)", text)
    succeeded = bool(exit_code and exit_code.group(1) == "0")
    return succeeded, re.sub(r"@EXIT:\d+\s*", "", text).strip()


def restore(checkpoint):
    """Roll the Taster's disk back to a checkpoint."""
    _request("POST", f"/checkpoints/{checkpoint}/restore")
