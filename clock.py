"""Real time from NTP over Wi-Fi, for timestamps and (later) WSPR scheduling.

The RTC is set to UTC. It is not battery backed, so every power-up starts
unsynced until Wi-Fi is up and an NTP server answers.
"""
import asyncio
import time

state = {"synced": False, "last_ms": None, "error": None}


def sync_once(host):
    import ntptime
    ntptime.host = host
    ntptime.timeout = 3
    ntptime.settime()
    state["synced"] = True
    state["last_ms"] = time.ticks_ms()
    state["error"] = None


async def keep_synced(net, cfg_source, interval_s=3600, retry_s=60):
    """Sync once Wi-Fi is up, then resync every interval_s."""
    while True:
        delay = 15
        if net["mode"] == "sta":
            try:
                sync_once(cfg_source()["ntp_host"])
                delay = interval_s
            except Exception as e:
                state["error"] = repr(e)
                delay = retry_s
        await asyncio.sleep(delay)


def status():
    out = {"synced": state["synced"], "error": state["error"], "utc": None,
           "last_sync_age_s": None}
    if state["synced"]:
        out["utc"] = "%04d-%02d-%02d %02d:%02d:%02dZ" % time.gmtime()[:6]
        out["last_sync_age_s"] = time.ticks_diff(time.ticks_ms(), state["last_ms"]) // 1000
    return out
