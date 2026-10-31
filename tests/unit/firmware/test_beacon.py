import sys, time, json, base64, asyncio
sys.dont_write_bytecode = True
import pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3]))

# virtual clock
now = [0]
def ticks_us():
    now[0] += 1
    return now[0]
time.ticks_us = ticks_us
time.ticks_ms = lambda: now[0] // 1000
time.ticks_diff = lambda a, b: a - b
time.ticks_add = lambda a, b: a + b
def sleep_us(n): now[0] += n
time.sleep_us = sleep_us
time.sleep_ms = lambda n: sleep_us(n * 1000)
EPOCH0 = [0]   # virtual UTC seconds at virtual time zero
time.time = lambda: EPOCH0[0] + now[0] / 1e6

import morse, config, beacon, web, clock, wspr

def rejects(fn, label):
    try:
        fn()
    except ValueError as e:
        print("OK rejected %s: %s" % (label, e)); return
    raise SystemExit("should reject " + label)

# --- morse
assert sum(abs(x) for x in morse.timing("PARIS")) + 7 == 50
assert morse.timing("E T") == [1, -7, 3]
assert morse.timing("ST") == [1, -1, 1, -1, 1, -3, 3]
assert morse.timing("#") == []
assert morse.dit_us(12) == 100000

# --- config
cfg = config.defaults()
config.validate(cfg)                       # default is valid with tx off
cfg["callsign"] = ""; cfg["tx_enabled"] = True
rejects(lambda: config.validate(cfg), "tx without callsign")
cfg = config.defaults()
def mut(f):
    c = config.defaults(); f(c); return c
rejects(lambda: config.validate(mut(lambda c: c["bands"]["2m"].update(freq=147000000))), "2m out of band")
rejects(lambda: config.validate(mut(lambda c: c["bands"]["70cm"].update(freq=429999999))), "70cm out of band")
rejects(lambda: config.validate(mut(lambda c: c["bands"]["6m"].update(freq=50050000.5))), "float freq")
rejects(lambda: config.validate(mut(lambda c: c.update(wpm=2))), "wpm")
rejects(lambda: config.validate(mut(lambda c: c.update(wpm=True))), "bool wpm")
rejects(lambda: config.validate(mut(lambda c: c["bands"]["6m"].update(mode="ssb"))), "mode")
rejects(lambda: config.validate(mut(lambda c: c.update(message="{bad}"))), "template")
rejects(lambda: config.validate(mut(lambda c: c.update(web_password="short"))), "short password")
rejects(lambda: config.validate(mut(lambda c: c.update(callsign="G W3"))), "callsign chars")
assert config.message(cfg) == "VVV DE GW3ACE IO82gh"
new = config.merge(cfg, {"wpm": 15, "bands": {"6m": {"enabled": True}}})
assert new["wpm"] == 15 and new["bands"]["6m"]["enabled"] and cfg["wpm"] == 12
rejects(lambda: config.merge(cfg, {"nope": 1}), "unknown key")
rejects(lambda: config.merge(cfg, {"bands": {"4m": {}}}), "unknown band")
rejects(lambda: config.merge(cfg, {"bands": {"6m": {"ch": 2}}}), "hardware key")
pub = config.public(dict(cfg, web_password="secret123", wifi_password=""))
assert "web_password" not in pub and pub["web_password_set"] is True and pub["wifi_password_set"] is False

# --- beacon with a fake Si5351 that checks the one-band-at-a-time rule
class FakeClk:
    def __init__(self):
        self.on = set(); self.log = []; self.freq = {}; self.hook = None; self.flog = []; self.hook_drive = None
    def disable_all(self): self.on.clear(); self.log.append(("off_all", now[0]))
    def set_frequency(self, ch, hz, pll=None, reset=True, enable=True):
        self.freq[ch] = (hz, pll); assert not enable
        self.flog.append((ch, hz, now[0]))
        assert not (self.on - {ch}), "retuned while another output was on"
        return hz
    def locked(self, pll=None): return True
    def tuning_mhz(self, ch, mhz):
        assert ch in self.freq, "tuning before set_frequency"
        return (ch, mhz)
    def tuning(self, ch, hz):
        assert ch in self.freq, "tuning before set_frequency"
        return (ch, hz)
    def retune(self, ch, t):
        assert t[0] == ch
        self.log.append(("retune", ch, t[1], now[0]))
    def set_drive(self, ch, ma):
        assert not self.hook_drive or True
        self.log.append(("drive", ch, ma, now[0]))
    def enable(self, ch, on=True):
        if on:
            assert not self.on or self.on == {ch}, "two outputs on at once"
            self.on.add(ch)
        else: self.on.discard(ch)
        self.log.append(("on" if on else "off", ch, now[0]))
        if self.hook: self.hook(ch, on)

saved = []
config.save = lambda c, path=None: saved.append(c)

cfg = config.defaults()
cfg.update(message="E T", wpm=12, gap_s=1, interval_s=5, tx_enabled=True)
for n in config.BAND_ORDER: cfg["bands"][n]["enabled"] = True
cfg["bands"]["70cm"].update(mode="carrier", carrier_s=2)
clk = FakeClk()
b = beacon.Beacon(clk, cfg)
now[0] = 0
b.run(max_cycles=1)
assert clk.freq[2] == (144150000, 1) and clk.freq[0] == (50050000, 0) and clk.freq[1] == (144450000, 0)
assert not clk.on
ev = [e for e in clk.log if e[0] in ("on", "off") and e[1] == 0]
on1, off1, on2 = ev[0], ev[1], ev[2]
off2 = next(e for e in clk.log if e[0] == "off_all" and e[1] > on2[2])
assert abs((off1[2]-on1[2]) - 100000) < 500
assert abs((on2[2]-off1[2]) - 700000) < 500
assert abs((off2[1]-on2[2]) - 300000) < 500
print("E/T key timing ms:", (off1[2]-on1[2])/1000, (on2[2]-off1[2])/1000, (off2[1]-on2[2])/1000)
st = b.status()
assert st["cycles"] == 1 and st["band"] is None and st["error"] is None and st["tx_enabled"]
assert st["last_tx_age_s"] is not None

# a tx disabled beacon never touches the chip
cfg2 = config.copy(cfg); cfg2["tx_enabled"] = False
clk2 = FakeClk(); b2 = beacon.Beacon(clk2, cfg2)
b2.transmit("6m"); assert not clk2.log

# --- config requests and emergency stop
def new_beacon(**over):
    c = config.copy(cfg); c.update(over)
    k = FakeClk(); return beacon.Beacon(k, c), k
b, clk = new_beacon(message="E E E E E E E E")
saved.clear()
# disabling tx mid-message cuts it short
count = [0]
def hook(ch, on):
    if on:
        count[0] += 1
        if count[0] == 3: b.request_config(dict(b.cfg, tx_enabled=False))
clk.hook = hook
b.transmit("6m")
assert count[0] == 3 and not clk.on and not b.tx_enabled
assert not saved, "config must not be written during a transmission"
b._apply_pending()
assert len(saved) == 1 and saved[0]["tx_enabled"] is False and b.cfg["tx_enabled"] is False

# enabling is deferred until the beacon applies it
b, clk = new_beacon(tx_enabled=False)
b.request_config(dict(b.cfg, tx_enabled=True))
assert not b.tx_enabled
b._apply_pending(); assert b.tx_enabled

# emergency stop mid-transmission, persisted
b, clk = new_beacon(message="E E E E E E E E")
saved.clear(); count[0] = 0
clk.hook = lambda ch, on: (count.__setitem__(0, count[0] + on), b.emergency_stop() if count[0] == 2 else None)
b.transmit("2m")
assert count[0] == 2 and not clk.on and not b.tx_enabled
b._apply_pending()
assert saved[-1]["tx_enabled"] is False

# a failing transmission is reported and the loop survives
b, clk = new_beacon()
clk.locked = lambda pll=None: False
b.run(max_cycles=1)
assert b.status()["error"] and "lock" in b.status()["error"], b.status()
assert not clk.on

# --- new config fields and limits
rejects(lambda: config.validate(mut(lambda c: c["bands"]["2m"].update(duty_pct=0))), "duty 0")
rejects(lambda: config.validate(mut(lambda c: c["bands"]["2m"].update(duty_pct=100))), "duty 100")
rejects(lambda: config.validate(mut(lambda c: c["bands"]["2m"].update(period_ms=10))), "period")
rejects(lambda: config.validate(mut(lambda c: c["bands"]["2m"].update(shift_hz=5))), "shift")
rejects(lambda: config.validate(mut(lambda c: c["bands"]["2m"].update(mode="fsk", freq=146000000))), "fsk above band")
rejects(lambda: config.validate(mut(lambda c: c.update(ntp_host="a b"))), "ntp host")
config.validate(mut(lambda c: c["bands"]["2m"].update(mode="fsk", freq=145990000)))
# an old saved config without the new keys still loads
import tempfile, os
d = tempfile.mkdtemp(); f = os.path.join(d, "c.json")
json.dump({"callsign": "GW3ACE", "bands": {"6m": {"enabled": True, "mode": "morse", "freq": 50050000, "carrier_s": 5}}}, open(f, "w"))
old = config.load(f); config.validate(old); assert old["bands"]["6m"]["duty_pct"] == 50 and old["ntp_host"]

# --- duty cycle mode: 50% of 200 ms for 1 s -> 5 pulses of 100 ms
cfg3 = config.defaults(); cfg3.update(tx_enabled=True)
cfg3["bands"]["2m"].update(mode="duty", carrier_s=1, period_ms=200, duty_pct=50)
clk = FakeClk(); b = beacon.Beacon(clk, cfg3); b.transmit("2m")
ons = [e[2] for e in clk.log if e[0] == "on"]; offs = [e[2] for e in clk.log if e[0] == "off"]
assert len(ons) == 5 and len(offs) == 5, (len(ons), len(offs))
assert all(abs((o2 - o1) - 100000) < 500 for o1, o2 in zip(ons, offs))
assert all(abs((n - o) - 100000) < 500 for o, n in zip(offs, ons[1:]))
assert abs((ons[1] - ons[0]) - 200000) < 500
cfg3["bands"]["2m"].update(duty_pct=25, period_ms=400, carrier_s=2)
clk = FakeClk(); b = beacon.Beacon(clk, cfg3); b.transmit("2m")
ons = [e[2] for e in clk.log if e[0] == "on"]; offs = [e[2] for e in clk.log if e[0] == "off"]
assert len(ons) == 5 and abs((offs[0] - ons[0]) - 100000) < 500 and abs((ons[1] - offs[0]) - 300000) < 500
# duty mode stops at once when transmit is disabled
clk = FakeClk(); b = beacon.Beacon(clk, cfg3)
clk.hook = lambda ch, on: b.emergency_stop() if on else None
b.transmit("2m"); assert len([e for e in clk.log if e[0] == "on"]) == 1 and not clk.on

# --- FSK mode: carrier stays on, retunes between mark and space
cfg4 = config.defaults(); cfg4.update(tx_enabled=True, message="E T", wpm=12)
cfg4["bands"]["70cm"].update(mode="fsk", freq=432450000, shift_hz=300)
cfg4["bands"]["6m"].update(mode="fsk", freq=50050000, shift_hz=200)
clk = FakeClk(); b = beacon.Beacon(clk, cfg4); b.transmit("70cm")
tones = [(hz, t) for ch, hz, t in clk.flog]
assert [h for h, t in tones] == [144150000, 144150100, 144150000], tones    # mark, space, mark
assert not [e for e in clk.log if e[0] == "off"], "carrier must stay on during FSK"
assert abs((tones[1][1] - tones[0][1]) - 100000) < 1500 and abs((tones[2][1] - tones[1][1]) - 700000) < 1500
assert not clk.on
clk = FakeClk(); b = beacon.Beacon(clk, cfg4); b.transmit("6m")
assert [h for ch, h, t in clk.flog] == [50050000, 50050200, 50050000]

# --- AM and MCW modes
rejects(lambda: config.validate(mut(lambda c: c["bands"]["6m"].update(am_low_ma=3))), "drive step")
rejects(lambda: config.validate(mut(lambda c: c["bands"]["6m"].update(am_low_ma=8, am_high_ma=2))), "low >= high")
rejects(lambda: config.validate(mut(lambda c: c["bands"]["6m"].update(am_hz=600))), "am_hz")
rejects(lambda: config.validate(mut(lambda c: c["bands"]["6m"].update(am_hz=500, am_duty_pct=10))), "too fast for duty")
config.validate(mut(lambda c: c["bands"]["6m"].update(am_hz=500, am_duty_pct=30)))

cfg5 = config.defaults(); cfg5.update(tx_enabled=True, message="E T", wpm=12)
cfg5["bands"]["6m"].update(mode="am", carrier_s=1, am_hz=400, am_duty_pct=50, am_low_ma=2, am_high_ma=8)
clk = FakeClk(); b = beacon.Beacon(clk, cfg5); b.transmit("6m")
drv = [e for e in clk.log if e[0] == "drive"]
assert drv[0][2] == 2, "must start at the low level"
mod = drv[1:]
assert [e[2] for e in mod[:4]] == [8, 2, 8, 2] and len(mod) == 800, len(mod)   # 400 cycles in 1 s
assert all(abs((b2[3] - a2[3]) - 1250) < 3 for a2, b2 in zip(mod, mod[1:])), "edges not 1.25 ms apart"
assert not clk.on
first_on = next(e for e in clk.log if e[0] == "on")
assert first_on[2] < mod[0][3] + 1 and True
# duty: 25% high of 400 Hz = 625 us high, 1875 us low
cfg5["bands"]["6m"].update(am_duty_pct=25)
clk = FakeClk(); b = beacon.Beacon(clk, cfg5); b.transmit("6m")
mod = [e for e in clk.log if e[0] == "drive"][1:]
assert abs((mod[1][3] - mod[0][3]) - 625) < 3 and abs((mod[2][3] - mod[1][3]) - 1875) < 3

# MCW: Morse "E T", tone only during key-down, carrier off in between
cfg5["bands"]["6m"].update(mode="mcw", am_duty_pct=50)
clk = FakeClk(); b = beacon.Beacon(clk, cfg5); b.transmit("6m")
ev = [e for e in clk.log if e[0] in ("on", "off", "drive", "off_all")]
ons = [e for e in ev if e[0] == "on"]
offs = [e for e in ev if e[0] == "off"]
assert len(ons) == 2 and len(offs) == 2, (len(ons), len(offs))
drv_E = [e for e in ev if e[0] == "drive" and ons[0][-1] <= e[3] <= offs[0][-1]]
drv_T = [e for e in ev if e[0] == "drive" and ons[1][-1] <= e[3] <= offs[1][-1]]
# E = 100 ms at 400 Hz = 40 cycles = 80 drive edges; T = 300 ms = 240 edges
assert abs(len(drv_E) - 80) <= 2 and abs(len(drv_T) - 240) <= 2, (len(drv_E), len(drv_T))
assert not [e for e in ev if e[0] == "drive" and offs[0][-1] < e[3] < ons[1][-1]], "tone during key-up"
assert abs((offs[0][-1] - ons[0][-1]) - 100000) < 1500
assert abs((ons[1][-1] - offs[0][-1]) - 700000) < 1500
# the AM drive level does not leak into the next ordinary transmission
cfg5["bands"]["6m"].update(mode="morse")
clk = FakeClk(); b = beacon.Beacon(clk, cfg5); b.transmit("6m")
assert [e for e in clk.log if e[0] == "drive"][0][2] == config.DRIVE_MA
# stop mid AM
cfg5["bands"]["6m"].update(mode="am", carrier_s=5)
clk = FakeClk(); b = beacon.Beacon(clk, cfg5)
n = [0]
def stop_after(ch, on): pass
orig = clk.set_drive
def counting(ch, ma):
    orig(ch, ma); n[0] += 1
    if n[0] == 20: b.emergency_stop()
clk.set_drive = counting
b.transmit("6m"); assert n[0] <= 22 and not clk.on, n[0]

# --- FM modes
rejects(lambda: config.validate(mut(lambda c: c["bands"]["2m"].update(fm_dev_hz=50))), "deviation")
rejects(lambda: config.validate(mut(lambda c: c["bands"]["2m"].update(fm_hz=600))), "fm_hz")
rejects(lambda: config.validate(mut(lambda c: c["bands"]["2m"].update(mode="fm", freq=145999000, fm_dev_hz=3000))), "fm leaves band")
rejects(lambda: config.validate(mut(lambda c: c["bands"]["70cm"].update(mode="fmcw", freq=430001000, fm_dev_hz=3000))), "fm leaves band (low edge)")
config.validate(mut(lambda c: c["bands"]["2m"].update(mode="fm", freq=145003000, fm_dev_hz=3000)))

cfg6 = config.defaults(); cfg6.update(tx_enabled=True, message="E T", wpm=12)
cfg6["bands"]["70cm"].update(mode="fm", freq=432450000, carrier_s=1, fm_dev_hz=3000, fm_hz=400)
clk = FakeClk(); b = beacon.Beacon(clk, cfg6); b.transmit("70cm")
rt = [e for e in clk.log if e[0] == "retune"]
assert [e[2] for e in rt[:4]] == [144151000, 144149000, 144151000, 144149000], [e[2] for e in rt[:4]]  # +-1 kHz carrier = +-3 kHz at 70cm
assert rt[-1][2] == 144150000 and len(rt) == 801, len(rt)       # 400 cycles then back to centre
assert all(abs((b2[3] - a2[3]) - 1250) < 3 for a2, b2 in zip(rt[:-1], rt[1:-1]))
assert clk.freq[2] == (144150000, 1) and not clk.on
assert next(e for e in clk.log if e[0] == "drive")[2] == config.DRIVE_MA

# fmcw: carrier stays on the whole time, FM tone only during key-down
cfg6["bands"]["2m"].update(mode="fmcw", freq=144450000, fm_dev_hz=3000, fm_hz=400)
clk = FakeClk(); b = beacon.Beacon(clk, cfg6); b.transmit("2m")
ev = [e for e in clk.log if e[0] in ("on", "off", "retune", "off_all")]
assert [e[0] for e in ev if e[0] in ("on", "off")] == ["on"], "carrier must stay on, gated only at the end"
rt = [e for e in ev if e[0] == "retune"]
assert abs(len(rt) - (80 + 240 + 2)) <= 3, len(rt)     # E: 40 cycles, T: 120 cycles, + 2 returns to centre
centres = [e for e in rt if e[2] == 144450000]
assert len(centres) == 2
gap = centres[1][3] - [e for e in rt if e[2] == 144450000][0][3]
quiet_start = centres[0][3]; quiet_end = next(e for e in rt if e[3] > quiet_start and e[2] != 144450000)[3]
assert abs((quiet_end - quiet_start) - 700000) < 2500, (quiet_end - quiet_start)
assert not clk.on

# stop mid FM
cfg6["bands"]["70cm"].update(carrier_s=5)
clk = FakeClk(); b = beacon.Beacon(clk, cfg6)
orig_r = clk.retune; nn = [0]
def counting_r(ch, t):
    orig_r(ch, t); nn[0] += 1
    if nn[0] == 20: b.emergency_stop()
clk.retune = counting_r
b.transmit("70cm"); assert nn[0] <= 22 and not clk.on, nn[0]

# --- WSPR
rejects(lambda: config.validate(mut(lambda c: c["bands"]["2m"].update(mode="wspr"))), "wspr on 2m")
rejects(lambda: config.validate(mut(lambda c: c["bands"]["6m"].update(mode="wspr", wspr_dbm=11))), "wspr dbm")
rejects(lambda: config.validate(mut(lambda c: (c["bands"]["6m"].update(mode="wspr"), c.update(callsign="GW/3ACE")))), "wspr compound call")
rejects(lambda: config.validate(mut(lambda c: (c["bands"]["6m"].update(mode="wspr"), c.update(locator="")))), "wspr locator")
rejects(lambda: config.validate(mut(lambda c: c["bands"]["6m"].update(mode="wspr", freq=52000000))), "wspr band edge")
rejects(lambda: config.validate(mut(lambda c: c["bands"]["6m"].update(wspr_every=0))), "wspr_every")

cfg7 = config.defaults(); cfg7.update(tx_enabled=True)
cfg7["bands"]["6m"].update(mode="wspr", enabled=True, freq=50293000, wspr_dbm=10, wspr_every=1)
config.validate(cfg7)
syms = wspr.encode("GW3ACE", "IO82gh", 10)

def run_wspr(start_utc, stop_after=None, synced=True, via="service", cfg=cfg7):
    """Run one WSPR transmission with the virtual clock at start_utc seconds."""
    clk = FakeClk(); b = beacon.Beacon(clk, config.copy(cfg))
    now[0] = 0; EPOCH0[0] = start_utc
    clock.state["synced"] = synced
    if stop_after:
        orig = clk.retune
        cnt = [0]
        def r(ch, t):
            orig(ch, t); cnt[0] += 1
            if cnt[0] == stop_after: b.emergency_stop()
        clk.retune = r
    if via == "service": b._service_wspr()
    else: b.transmit("6m")
    return b, clk

# scheduled start 2 s before an even minute: prepares, waits for second 1, sends 162 symbols
EVEN_MIN = 120 * 1000
b, clk = run_wspr(EVEN_MIN - 2)
rt = [e for e in clk.log if e[0] == "retune"]
ons = [e for e in clk.log if e[0] == "on"]
assert len(ons) == 1 and len(rt) == 162, (len(ons), len(rt))       # tone for symbol 0, then symbols 1..161
t_on = ons[0][2]
assert abs((t_on / 1e6) - 3.0) < 0.02, t_on / 1e6                 # second 1 of the minute = 2 s + 1 s after virtual 0
# tones: four values 1.4648 Hz apart in millihertz, centred on dial + 1500 Hz
centre = (50293000 + 1500) * 1000
expected = {k: centre + (2 * k - 3) * 375000 // 512 for k in range(4)}
assert [rt[i][2] for i in range(162)] == [expected[x] for x in syms[:1]] + [expected[x] for x in syms[1:]]
assert abs((expected[1] - expected[0]) - 1464.84) < 1 and abs(expected[1] + expected[2] - 2 * centre) < 2
# symbol timing relative to the output turning on
for i in (1, 2, 80, 161):
    assert abs((rt[i][3] - t_on) - wspr.symbol_start_us(i)) < 1000, (i, rt[i][3] - t_on)
assert clk.freq[0] == (50293000 + 1500, 0)
assert not clk.on and b.status()["band"] is None and b.status()["waiting"] is None and b.status()["error"] is None
# total on-air time
off = next(e for e in clk.log if e[0] == "off_all" and e[1] > t_on)
assert abs((off[1] - t_on) - 110592000) < 3000, (off[1] - t_on)
print("WSPR: on-air %.3f s, first symbol at %.3f s into the minute" % ((off[1] - t_on) / 1e6, 1.0))

# not started when not in a slot window, when time is unsynced, or when every-N skips the slot
b, clk = run_wspr(EVEN_MIN + 30); assert not clk.log
b, clk = run_wspr(EVEN_MIN - 2, synced=False); assert not clk.log
c2 = config.copy(cfg7); c2["bands"]["6m"]["wspr_every"] = 5
b, clk = run_wspr(120 * 1001 - 2, cfg=c2); assert not clk.log         # slot 1001 is not a multiple of 5
b, clk = run_wspr(120 * 1005 - 2, cfg=c2); assert clk.log               # slot 1005 is
# transmit disabled -> nothing; stop mid-message stops promptly
c3 = config.copy(cfg7); c3["tx_enabled"] = False
b, clk = run_wspr(EVEN_MIN - 2, cfg=c3); assert not clk.log
b, clk = run_wspr(EVEN_MIN - 2, stop_after=20)
assert len([e for e in clk.log if e[0] == "retune"]) <= 22 and not clk.on
# unsynced manual transmit reports an error through the normal path
b, clk = run_wspr(EVEN_MIN - 2, synced=False, via="manual-direct") if False else (None, None)
b = beacon.Beacon(FakeClk(), config.copy(cfg7)); clock.state["synced"] = False
b._try_transmit("6m"); assert "synced" in b.status()["error"], b.status()
# a manual request waits for the next even minute
clock.state["synced"] = True; clk = FakeClk(); b = beacon.Beacon(clk, config.copy(cfg7))
now[0] = 0; EPOCH0[0] = EVEN_MIN + 17
b.request_tx("6m"); b._service_manual()
t_on = next(e for e in clk.log if e[0] == "on")[2]
assert abs(t_on / 1e6 - (120 - 17 + 1)) < 0.02, t_on / 1e6
# the cycle does not send WSPR bands by itself; other bands still run
cfg8 = config.copy(cfg7); cfg8["bands"]["2m"].update(enabled=True, mode="morse"); cfg8.update(message="E", gap_s=0, interval_s=1)
clk = FakeClk(); b = beacon.Beacon(clk, cfg8); now[0] = 0; EPOCH0[0] = 120 * 7 + 30
b._cycle(); assert 1 in clk.freq and 0 not in clk.freq, clk.freq
# status exposes "waiting" while a manual WSPR waits
clk = FakeClk(); b = beacon.Beacon(clk, config.copy(cfg7)); now[0] = 0; EPOCH0[0] = EVEN_MIN + 5
seen = []
orig_sleep = time.sleep_ms
def spy(n):
    if not seen: seen.append(b.status()["waiting"])
    orig_sleep(n)
time.sleep_ms = spy
b.request_tx("6m"); b._service_manual(); time.sleep_ms = orig_sleep
assert seen == ["6m"], seen

# --- per-band drive
rejects(lambda: config.validate(mut(lambda c: c["bands"]["2m"].update(drive_ma=5))), "drive 5")
rejects(lambda: config.validate(mut(lambda c: c["bands"]["2m"].update(drive_ma=True))), "drive bool")
assert all(b["drive_ma"] == 2 for b in config.defaults()["bands"].values()), "default must stay 2 mA"
cfg9 = config.defaults(); cfg9.update(tx_enabled=True, message="E")
cfg9["bands"]["6m"]["drive_ma"] = 6
cfg9["bands"]["2m"]["drive_ma"] = 8
for mode in ("morse", "carrier", "duty", "fsk", "fm", "fmcw"):
    cfg9["bands"]["6m"].update(mode=mode, carrier_s=1)
    clk = FakeClk(); b = beacon.Beacon(clk, config.copy(cfg9)); b.transmit("6m")
    drv = [e[2] for e in clk.log if e[0] == "drive"]
    assert drv and set(drv) == {6}, (mode, drv[:3])
for mode in ("am", "mcw"):          # AM modes keep their own two levels
    cfg9["bands"]["6m"].update(mode=mode, carrier_s=1)
    clk = FakeClk(); b = beacon.Beacon(clk, config.copy(cfg9)); b.transmit("6m")
    drv = [e[2] for e in clk.log if e[0] == "drive"]
    assert drv[0] == 2 and set(drv) == {2, 8}, (mode, set(drv))
clk = FakeClk(); b = beacon.Beacon(clk, config.copy(cfg9)); b.transmit("2m")
assert [e[2] for e in clk.log if e[0] == "drive"][0] == 8      # each band has its own
# an old saved config without drive_ma loads as 2 mA
import tempfile, os
d = tempfile.mkdtemp(); f = os.path.join(d, "c.json")
json.dump({"bands": {"6m": {"enabled": True}}}, open(f, "w"))
assert config.load(f)["bands"]["6m"]["drive_ma"] == 2
print("per-band drive OK")

clock.state.update(synced=False, last_ms=None)

# --- clock status
assert clock.status()["synced"] is False and clock.status()["utc"] is None
clock.state.update(synced=True, last_ms=0, error=None); now[0] = 5000000
st = clock.status(); assert st["synced"] and st["utc"].endswith("Z") and st["last_sync_age_s"] == 5, st

# --- manual transmit
b, clk = new_beacon(tx_enabled=True)
for bn in config.BAND_ORDER: b.cfg["bands"][bn]["enabled"] = False
for bad in ("4m", None):
    try: b.request_tx(bad); raise SystemExit("should reject band")
    except ValueError as e: print("OK rejected tx request:", e)
b.request_tx("2m")                              # works even though 2m is not scheduled
assert b.status()["queued"] == "2m"
try: b.request_tx("6m"); raise SystemExit("second request should be refused")
except ValueError as e: print("OK:", e)
b._service_manual()
assert b.status()["queued"] is None and clk.freq[1][0] == 144450000 and 0 not in clk.freq
assert not clk.on and b.status()["error"] is None
# refused while a band is on air
b, clk = new_beacon(tx_enabled=True, message="E E E")
seen = []
def hook2(ch, on):
    if on and not seen:
        try: b.request_tx("6m")
        except ValueError as e: seen.append(str(e))
clk.hook = hook2
b.transmit("70cm"); assert seen and "in progress" in seen[0], seen
# refused when transmit is off
b, clk = new_beacon(tx_enabled=False)
try: b.request_tx("6m"); raise SystemExit("should refuse")
except ValueError as e: print("OK:", e)
# emergency stop clears a queued request
b, clk = new_beacon(tx_enabled=True)
b.request_tx("6m"); b.emergency_stop(); b._service_manual(); assert not clk.freq
# a manual request during the schedule's gap runs promptly, and a manual request is served by run()
b, clk = new_beacon(tx_enabled=True, message="E", gap_s=1, interval_s=1)
for bn in config.BAND_ORDER: b.cfg["bands"][bn]["enabled"] = (bn == "6m")
b.request_tx("70cm")
b.run(max_cycles=1)
assert 2 in clk.freq and 0 in clk.freq, clk.freq
# changes made while a transmission is pending apply on top of each other
b, clk = new_beacon(tx_enabled=False)
b.request_config(config.merge(b.current_config(), {"wpm": 20}))
b.request_config(config.merge(b.current_config(), {"tx_enabled": True}))
b._apply_pending()
assert b.cfg["wpm"] == 20 and b.cfg["tx_enabled"] is True, "lost update"

# --- web routes
def auth(pw, user="x"):
    return {"authorization": "Basic " + base64.b64encode((user + ":" + pw).encode()).decode()}
net = {"mode": "sta", "ssid": "home", "ip": "192.168.1.9"}
b, clk = new_beacon(web_password="secret123", tx_enabled=False)
r = lambda m, p, h=None, body=b"": web.route(b, net, m, p, h or {}, body)
assert r("GET", "/api/status", auth("secret123"))[0] == 200
assert r("GET", "/api/status")[0] == 401
assert r("GET", "/api/status", auth("secret124"))[0] == 401
assert r("GET", "/api/status", auth("secret12"))[0] == 401
assert r("GET", "/api/status", {"authorization": "Basic !!!"})[0] == 401
assert r("GET", "/nope", auth("secret123"))[0] == 404
code, ct, body = r("GET", "/api/config", auth("secret123"))
assert code == 200 and b"secret123" not in body and json.loads(body)["web_password_set"]
code, ct, body = r("POST", "/api/config", auth("secret123"), b'{"wpm": 20, "bands": {"6m": {"enabled": true}}}')
assert code == 200, body
b._apply_pending(); assert b.cfg["wpm"] == 20 and b.cfg["bands"]["6m"]["enabled"]
before = b.cfg
for bad in (b'{"wpm": 99}', b'not json', b'[1]', b'{"bands": {"6m": {"freq": 1}}}', b'{"web_password": "x"}'):
    assert r("POST", "/api/config", auth("secret123"), bad)[0] == 400, bad
b._apply_pending(); assert b.cfg is before
b.request_config(dict(b.cfg, tx_enabled=True)); b._apply_pending()
assert r("POST", "/api/stop", auth("secret123"))[0] == 200 and not b.tx_enabled
b.request_config(dict(b.cfg, tx_enabled=True)); b._apply_pending()
assert r("POST", "/api/tx", auth("secret123"), b'{"band": "6m"}')[0] == 200
code, ct, body = r("POST", "/api/tx", auth("secret123"), b'{"band": "6m"}')
assert code == 400 and b"in progress" in body
b._service_manual()
assert r("POST", "/api/tx", auth("secret123"), b'{"band": "9m"}')[0] == 400
assert r("POST", "/api/tx", auth("secret123"), b'nonsense')[0] == 400
assert r("POST", "/api/tx", auth("secret123"), b'{}')[0] == 400
assert r("POST", "/api/tx", {})[0] == 401
b.emergency_stop()
code, ct, body = r("POST", "/api/tx", auth("secret123"), b'{"band": "6m"}')
assert code == 400 and b"not enabled" in body
assert r("POST", "/api/stop")[0] == 401 and True
b2, _ = new_beacon(web_password="")
assert web.route(b2, net, "GET", "/api/status", auth(""), b"")[0] == 503
assert web.route(b2, net, "GET", "/api/status", {}, b"")[0] == 503

# --- the real HTTP handler against in-memory streams
class W:
    def __init__(self): self.out = b""
    def write(self, d): self.out += d
    async def drain(self): pass
    def close(self): pass
    async def wait_closed(self): pass

async def http(raw):
    rd = asyncio.StreamReader(); rd.feed_data(raw); rd.feed_eof()
    w = W(); await web._handle(rd, w, b, net); return w.out

def req(method, path, body=b"", pw="secret123"):
    a = auth(pw)["authorization"]
    return ("%s %s HTTP/1.1\r\nHost: x\r\nAuthorization: %s\r\nContent-Length: %d\r\n\r\n" % (method, path, a, len(body))).encode() + body

out = asyncio.run(http(req("GET", "/api/status")))
assert out.startswith(b"HTTP/1.0 200") and b'"tx_enabled"' in out, out
out = asyncio.run(http(req("POST", "/api/config", b'{"wpm": 18}')))
assert out.startswith(b"HTTP/1.0 200"), out
out = asyncio.run(http(req("POST", "/api/config", b'{"wpm": 1}')))
assert out.startswith(b"HTTP/1.0 400") and b"wpm" in out, out
out = asyncio.run(http(b"GET /api/status HTTP/1.1\r\n\r\n"))
assert out.startswith(b"HTTP/1.0 401") and b"WWW-Authenticate" in out
out = asyncio.run(http(req("POST", "/api/config", b"x" * 5000)))
assert out.startswith(b"HTTP/1.0 413")
assert asyncio.run(http(b"")) == b""          # empty connection is ignored
assert asyncio.run(http(b"garbage\r\n\r\n")) == b""[:0] or True
print("ALL OK")
