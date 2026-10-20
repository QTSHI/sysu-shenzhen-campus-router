"""Render one bounded-recovery stock service. No device actions on import."""
import json
import re

DIRECTORY = "/data/usr/sysu-campus-auth/service"
STATE_FIELDS = {"kind", "phase", "reason", "boot_id", "uptime_seconds", "runner_pid",
                "client_pid", "observer_pid", "attempt", "recovery_used", "eap_success_seen",
                "failure_latched", "wan_carrier", "observer_segment", "observer_exit_code"}
PHASES = {"starting", "waiting-wan", "checking", "authenticating", "online", "latched", "stopped"}
REASONS = {"startup", "startup-wait", "checking-live-gate", "single-attempt", "eap-success",
           "eap-success-renew-failed", "local-stop", "persistent-latch", "carrier-unavailable",
           "link-lost-during-auth", "recovery-budget-exhausted", "one-link-recovery-pending",
           "eap-failure", "client-exited", "auth-timeout", "observer-error", "observer-not-ready",
           "monitor-gate-failed", "start-gate-failed", "attempt-intent-conflict",
           "attempt-intent-invalid", "supervisor-error", "supervisor-missing-no-retry",
           "previous-attempt-unknown", "stop-unverified-child"}


def parse_state(raw):
    if not isinstance(raw, bytes) or not 1 <= len(raw) <= 4096:
        raise ValueError("Invalid bounded service status")
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result: raise ValueError("Duplicate service state field")
            result[key] = value
        return result
    value = json.loads(raw.decode("ascii"), object_pairs_hook=pairs)
    if (not isinstance(value, dict) or set(value) != STATE_FIELDS
            or value["kind"] != "stock_campus_service_state_v1"
            or value["phase"] not in PHASES or value["reason"] not in REASONS
            or not isinstance(value["boot_id"], str)
            or not re.fullmatch(r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}", value["boot_id"])):
        raise ValueError("Unexpected service state schema")
    for key in ("uptime_seconds", "runner_pid", "client_pid", "observer_pid", "attempt", "recovery_used", "observer_segment"):
        if type(value[key]) is not int or not 0 <= value[key] <= 2147483647:
            raise ValueError("Invalid numeric service state")
    if not 1 <= value["runner_pid"] or value["attempt"] > 2 or value["recovery_used"] > 1:
        raise ValueError("Service attempt budget exceeded")
    for key in ("eap_success_seen", "failure_latched"):
        if type(value[key]) is not bool: raise ValueError("Invalid boolean service state")
    if value["wan_carrier"] is not None and (type(value["wan_carrier"]) is not int or value["wan_carrier"] not in (0, 1)):
        raise ValueError("Invalid service carrier")
    if value["observer_exit_code"] is not None and (type(value["observer_exit_code"]) is not int or not 0 <= value["observer_exit_code"] <= 255):
        raise ValueError("Invalid observer exit code")
    return value


def build_runner(directory=DIRECTORY, minieap_sha=None, observer_sha=None):
    if directory != DIRECTORY:
        raise ValueError("Only the reviewed persistent service directory is allowed")
    if any(not isinstance(v, str) or not re.fullmatch(r"[0-9a-f]{64}", v)
           for v in (minieap_sha, observer_sha)):
        raise ValueError("Pinned binary digests are required")
    return _SCRIPT.replace("@MINI@", minieap_sha).replace("@OBS@", observer_sha).encode("ascii")


_SCRIPT = r'''#!/bin/sh
set -eu
umask 077
PATH=/usr/sbin:/usr/bin:/sbin:/bin
export PATH
D=/data/usr/sysu-campus-auth/service
R=/tmp/sysu-campus-service
C=/data/usr/sysu-campus-auth/minieap.conf
MINISHA=@MINI@
OBSSHA=@OBS@
CP=; OP=; GP=; SUCCESS=false; FAILED=false; PHASE=starting; REASON=startup
ATTEMPT=0; RECOVERY=0; OP_RC=null; NEXT_SAMPLE=0; AUTH_DEADLINE=0; SEGMENT=0
now() { read up rest < /proc/uptime; printf '%s\n' "${up%%.*}"; }
hash() { openssl dgst -sha256 "$1" 2>/dev/null | awk '{print $NF}'; }
safe_file() { test -f "$1" && test ! -L "$1" && test "$(stat -c '%u:%a' "$1")" = "0:$2"; }
safe_dir() { test -d "$1" && test ! -L "$1" && test "$(stat -c '%u:%a' "$1")" = '0:700'; }
boot() { cat /proc/sys/kernel/random/boot_id; }
valid_install() {
 safe_dir "$D" && safe_file "$C" 600 && safe_file "$D/runner.sh" 700 && safe_file "$D/gate.lua" 700 && safe_file "$D/minieap" 700 && safe_file "$D/eapol-observer" 700 || return 1
 safe_file "$D/runner.sha256" 600 && safe_file "$D/gate.sha256" 600 || return 1
 test "$(hash "$D/runner.sh")" = "$(cat "$D/runner.sha256")" && test "$(hash "$D/gate.lua")" = "$(cat "$D/gate.sha256")" || return 1
 test "$(hash "$D/minieap")" = "$MINISHA" && test "$(hash "$D/eapol-observer")" = "$OBSSHA"
}
enabled() { safe_file "$D/enabled" 600 && test "$(cat "$D/enabled")" = v1; }
runtime() {
 if test -e "$R" || test -L "$R"; then safe_dir "$R"; else mkdir -m 700 "$R"; fi
}
start_tick() { awk '{print $22}' "/proc/$1/stat" 2>/dev/null; }
own_runner() {
 safe_file "$R/runner.meta" 600 || return 1
 read rp rt < "$R/runner.meta" || return 1
 case "$rp:$rt" in *[!0-9:]*|:*) return 1;; esac
 test -n "$rp" && test -n "$rt" && test -d "/proc/$rp" || return 1
 test "$(start_tick "$rp")" = "$rt" || return 1
 test "$(readlink /proc/$rp/exe 2>/dev/null || true)" = "$(readlink -f /bin/sh)" || return 1
 test "$(tr '\000' '\n' < /proc/$rp/cmdline)" = "$(printf '%s\n' /bin/sh "$D/runner.sh" run)"
}
own_child() {
 p="$1"; exe="$2"
 case "$p" in ''|*[!0-9]*) return 1;; esac
 test -f "/proc/$p/status" || return 1
 awk -v owner="$$" '$1=="PPid:" && $2==owner {ok=1} END {exit !ok}' "/proc/$p/status" || return 1
 test "$(readlink /proc/$p/exe 2>/dev/null || true)" = "$(readlink -f "$exe")"
}
child_alive() {
 p="$1"
 case "$p" in ''|*[!0-9]*) return 1;; esac
 test -f "/proc/$p/status" || return 1
 awk -v owner="$$" '$1=="PPid:" && $2==owner {parent=1} $1=="State:" && $2!="Z" {alive=1} END {exit !(parent && alive)}' "/proc/$p/status"
}
stop_child() {
 p="$1"; exe="$2"
 if own_child "$p" "$exe"; then
  kill -TERM "$p" 2>/dev/null || true
  sleep 1
  if own_child "$p" "$exe"; then kill -KILL "$p" 2>/dev/null || true; fi
 fi
 # An unverified executable may still be pre-exec. Never wait without a bound.
 if ! child_alive "$p"; then wait "$p" 2>/dev/null || true; fi
}
latch() {
 FAILED=true; REASON="$1"; PHASE=latched
 if test ! -e "$D/fault" && test ! -L "$D/fault"; then
  mkdir -m 700 "$D/fault" || return 1
  printf '%s\n' "$REASON" > "$D/fault/reason"
  printf '%s\n' "$(boot)" > "$D/fault/boot-id"
  chmod 600 "$D/fault/reason" "$D/fault/boot-id"
 fi
}
state() {
 carrier=$(cat /sys/class/net/eth0.1/carrier 2>/dev/null || true)
 case "$carrier" in 0|1) :;; *) carrier=null;; esac
 printf '{"kind":"stock_campus_service_state_v1","phase":"%s","reason":"%s","boot_id":"%s","uptime_seconds":%s,"runner_pid":%s,"client_pid":%s,"observer_pid":%s,"attempt":%s,"recovery_used":%s,"eap_success_seen":%s,"failure_latched":%s,"wan_carrier":%s,"observer_segment":%s,"observer_exit_code":%s}\n' "$PHASE" "$REASON" "$(boot)" "$(now)" "$$" "${CP:-0}" "${OP:-0}" "$ATTEMPT" "$RECOVERY" "$SUCCESS" "$FAILED" "$carrier" "$SEGMENT" "$OP_RC" > "$R/state.json.new"
 mv "$R/state.json.new" "$R/state.json"
}
sample() {
 state
 # RAM-only bounded summary. No packet bodies, command lines, or credentials.
 if test ! -f "$R/online.jsonl" || test "$(stat -c %s "$R/online.jsonl")" -lt 1048576; then cat "$R/state.json" >> "$R/online.jsonl"; fi
 NEXT_SAMPLE=$(( $(now)+60 ))
}
gate() {
 mode="$1"
 if test "$mode" = monitor; then /usr/bin/lua "$D/gate.lua" monitor "$CP" "$$" </dev/null >/dev/null 2>&1 &
 else /usr/bin/lua "$D/gate.lua" start </dev/null >/dev/null 2>&1 & fi
 GP=$!; end=$(( $(now)+20 ))
 while child_alive "$GP"; do
  if test "$(now)" -ge "$end"; then stop_child "$GP" /usr/bin/lua; GP=; return 1; fi
  sleep 1
 done
 rc=0; wait "$GP" 2>/dev/null || rc=$?; GP=
 test "$rc" = 0
}
archive_segment() {
 if test -f "$R/eap.current.jsonl"; then
  current=$(stat -c %s "$R/eap.current.jsonl")
  total=0; if test -f "$R/eap_metadata.jsonl"; then total=$(stat -c %s "$R/eap_metadata.jsonl"); fi
  if test $(( current+total )) -le 1048576; then cat "$R/eap.current.jsonl" >> "$R/eap_metadata.jsonl"; fi
 fi
}
observer() {
 : > "$R/eap.current.jsonl"
 (ulimit -f 256; exec "$D/eapol-observer" --interface eth0.1 --seconds 300) </dev/null > "$R/eap.current.jsonl" 2>/dev/null &
 OP=$!; OP_RC=null; SEGMENT=$(( SEGMENT+1 )); idx=$(cat /sys/class/net/eth0.1/ifindex)
 for n in 1 2 3 4 5; do
  child_alive "$OP" || break
  if ! own_child "$OP" "$D/eapol-observer"; then sleep 1; continue; fi
  for f in /proc/$OP/fd/*; do
   sock=$(readlink "$f" 2>/dev/null || true)
   case "$sock" in socket:\[*\]) ino=${sock#socket:[}; ino=${ino%]}
    if awk -v ino="$ino" -v idx="$idx" '$4=="888e" && $5==idx && $9==ino {ok=1} END {exit !ok}' /proc/net/packet; then return 0; fi;; esac
  done
  sleep 1
 done
 return 1
}
stop_attempt() {
 if test -n "$CP"; then stop_child "$CP" "$D/minieap"; if child_alive "$CP"; then latch stop-unverified-child; else CP=; fi; fi
 if test -n "$OP"; then stop_child "$OP" "$D/eapol-observer"; if child_alive "$OP"; then latch stop-unverified-child; else OP=; fi; fi
 archive_segment
}
begin_attempt() {
 SUCCESS=false; PHASE=checking; REASON=checking-live-gate; state
 valid_install && gate start || { latch start-gate-failed; return 1; }
 if ! observer; then latch observer-not-ready; return 1; fi
 # Write intent before starting the sole credential-using process.
 (set -C; printf '%s\n' "$(boot)" > "$D/attempt.pending") || { latch attempt-intent-conflict; return 1; }
 safe_file "$D/attempt.pending" 600 || { latch attempt-intent-invalid; return 1; }
 ATTEMPT=$(( ATTEMPT+1 )); printf '%s\n' "$ATTEMPT" > "$R/auth-attempt-$ATTEMPT.intent"
 "$D/minieap" --conf-file "$C" </dev/null >/dev/null 2>&1 &
 CP=$!; AUTH_DEADLINE=$(( $(now)+65 )); PHASE=authenticating; REASON=single-attempt; state
}
cleanup() {
 rc=$?; trap - EXIT; trap '' HUP INT TERM
 if test -n "$GP"; then stop_child "$GP" /usr/bin/lua; GP=; fi
 stop_attempt
 if test "$rc" != 0 && test "$FAILED" != true; then latch supervisor-error || true; fi
 PHASE=stopped; state || true
}
case "${1:-}" in
ensure)
 valid_install || exit 20
 enabled || exit 0
 if test -e "$D/fault" || test -L "$D/fault"; then exit 0; fi
 runtime || exit 21
 mkdir -m 700 "$R/ensure.lock" 2>/dev/null || exit 0
 trap 'rmdir "$R/ensure.lock" 2>/dev/null || true' EXIT
 if own_runner; then exit 0; fi
 if test -e "$D/attempt.pending" || test -L "$D/attempt.pending"; then latch previous-attempt-unknown; exit 0; fi
 if test -e "$R/boot.start.intent" || test -L "$R/boot.start.intent"; then latch supervisor-missing-no-retry; exit 0; fi
 if test -e "$R/stop.request" || test -L "$R/stop.request"; then exit 0; fi
 (set -C; printf '%s\n' "$(boot)" > "$R/boot.start.intent")
 trap '' HUP
 /bin/sh "$D/runner.sh" run </dev/null >/dev/null 2>&1 &
 printf 'service-launch-requested\n'
 ;;
run)
 valid_install && enabled && runtime || exit 20
 test ! -e "$D/fault" && test ! -L "$D/fault" || exit 0
 if test -e "$D/attempt.pending" || test -L "$D/attempt.pending"; then latch previous-attempt-unknown; exit 0; fi
 safe_file "$R/boot.start.intent" 600 || exit 21
 mkdir -m 700 "$R/runner.lock" 2>/dev/null || exit 0
 trap cleanup EXIT
 trap 'REASON=local-stop; exit 0' INT TERM
 printf '%s %s\n' "$$" "$(start_tick $$)" > "$R/runner.meta"
 PHASE=waiting-wan; REASON=startup-wait; sample
 while :; do
  if ! enabled || test -e "$R/stop.request"; then REASON=local-stop; exit 0; fi
  test ! -e "$D/fault" && test ! -L "$D/fault" || { FAILED=true; REASON=persistent-latch; exit 0; }
  carrier=$(cat /sys/class/net/eth0.1/carrier 2>/dev/null || true)
  case "$carrier" in 0|1) :;; *) latch carrier-unavailable; exit 0;; esac
  if test -z "$CP"; then
   if test "$carrier" = 1; then
    # Three seconds of stable carrier; no DHCP or authentication while down.
    sleep 3
    test "$(cat /sys/class/net/eth0.1/carrier 2>/dev/null || true)" = 1 || continue
    begin_attempt || exit 0
   fi
  elif test "$carrier" = 0; then
   if test "$SUCCESS" != true; then latch link-lost-during-auth; exit 0; fi
   stop_attempt
   if test "$RECOVERY" != 0 || test -e "$R/recovery.used"; then latch recovery-budget-exhausted; exit 0; fi
   (set -C; printf '1\n' > "$R/recovery.used")
   RECOVERY=1; PHASE=waiting-wan; REASON=one-link-recovery-pending; state
  else
   if grep -q '"direction":"in".*"eap_code":4,' "$R/eap.current.jsonl"; then latch eap-failure; exit 0; fi
   if ! own_child "$CP" "$D/minieap"; then latch client-exited; exit 0; fi
   if test "$SUCCESS" = false && grep -q '"direction":"in".*"eap_code":3,' "$R/eap.current.jsonl"; then
    safe_file "$D/attempt.pending" 600 || { latch attempt-intent-invalid; exit 0; }
    rm "$D/attempt.pending"
    SUCCESS=true; PHASE=online; REASON=eap-success; state
    if ! ubus -t 5 call network.interface.wan renew '{}' >/dev/null 2>&1; then REASON=eap-success-renew-failed; state; fi
   fi
   if test "$SUCCESS" = false && test "$(now)" -ge "$AUTH_DEADLINE"; then latch auth-timeout; exit 0; fi
   if ! own_child "$OP" "$D/eapol-observer"; then
    OP_RC=0; wait "$OP" 2>/dev/null || OP_RC=$?; OP=
    if test "$OP_RC" != 0; then latch observer-error; exit 0; fi
    archive_segment
    if ! observer; then latch observer-not-ready; exit 0; fi
   fi
  fi
  if test "$(now)" -ge "$NEXT_SAMPLE"; then
   if test -n "$CP" && test "$carrier" = 1; then gate monitor || { latch monitor-gate-failed; exit 0; }; fi
   sample
  fi
  sleep 1
 done
 ;;
status)
 if safe_dir "$R" && safe_file "$R/state.json" 600 && enabled && test ! -e "$D/fault" && test ! -L "$D/fault" && own_runner; then cat "$R/state.json"; else printf '{"kind":"stock_campus_service_state_v1","phase":"not-running"}\n'; fi
 ;;
stop|disable)
 if test "$1" = disable; then
  if test -e "$D/enabled" || test -L "$D/enabled"; then safe_file "$D/enabled" 600 || exit 30; rm "$D/enabled"; fi
 fi
 runtime || exit 21
 : > "$R/stop.request"
 for n in 1 2 3 4 5 6 7 8 9 10; do if ! own_runner; then printf 'service-stop-observed\n'; exit 0; fi; sleep 1; done
 if own_runner; then kill -TERM "$rp" 2>/dev/null || true; fi
 # Never kill an orphan by an unverified PID or automatically restart it.
 printf 'service-stop-requested-verify-no-client\n'
 ;;
*) exit 64;;
esac
'''
