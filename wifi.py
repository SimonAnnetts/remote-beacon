"""Wi-Fi: join the configured network, else fall back to a setup access point."""
import asyncio
import time

import network

AP_SSID = "remote-beacon"
HOSTNAME = "remote-beacon"


def start(cfg, timeout_s=20):
    """Return a dict describing the network: mode "sta", "ap" or "none"."""
    try:
        network.hostname(HOSTNAME)
    except (AttributeError, ValueError):
        pass
    ssid = cfg["wifi_ssid"]
    if ssid:
        sta = network.WLAN(network.STA_IF)
        sta.active(True)
        sta.connect(ssid, cfg["wifi_password"] or None)
        deadline = time.ticks_add(time.ticks_ms(), timeout_s * 1000)
        while not sta.isconnected() and time.ticks_diff(deadline, time.ticks_ms()) > 0:
            time.sleep_ms(200)
        if sta.isconnected():
            return {"mode": "sta", "ssid": ssid, "ip": sta.ifconfig()[0]}
        sta.active(False)
    if cfg["web_password"]:
        # The setup network is protected with the web password (WPA2).
        ap = network.WLAN(network.AP_IF)
        ap.config(ssid=AP_SSID, password=cfg["web_password"])
        ap.active(True)
        return {"mode": "ap", "ssid": AP_SSID, "ip": ap.ifconfig()[0]}
    return {"mode": "none", "ssid": "", "ip": ""}


async def keep_connected(net, cfg_source):
    """Reconnect the station interface if the link drops."""
    sta = network.WLAN(network.STA_IF)
    while True:
        await asyncio.sleep(15)
        if net["mode"] != "sta":
            continue
        if not sta.isconnected():
            cfg = cfg_source()
            sta.connect(cfg["wifi_ssid"], cfg["wifi_password"] or None)
        else:
            net["ip"] = sta.ifconfig()[0]
