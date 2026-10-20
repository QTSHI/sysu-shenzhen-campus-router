"""OFFLINE ONLY: truthful v2 status and a rolling, bounded link-recovery policy.

No installer, device connection, fault clearing, or live invocation exists here.
The running v1 and its observers remain frozen. New readers/observers must
explicitly support this v2 schema before this candidate may be considered.
"""
import hashlib
import json
from pathlib import Path
import re

BASE=Path(__file__).resolve().parent
PARENT_SHA='9a4030a341559633e6374381cbdb78447590de402719e9396d84c9a4c9ed0808'
KIND='stock_campus_service_state_v2'
DIRECTORY='/data/usr/sysu-campus-auth/service'


def parent_module():
    if hashlib.sha256((BASE/'stock_persistent_runner_shutdown.py').read_bytes()).hexdigest()!=PARENT_SHA:
        raise ValueError('Frozen shutdown renderer changed')
    import stock_persistent_runner_shutdown
    return stock_persistent_runner_shutdown


def change(text,before,after):
    if text.count(before)!=1:raise ValueError('Frozen runner replacement shape changed')
    return text.replace(before,after,1)


_base=parent_module().parent_module().old_module()
STATE_FIELDS=frozenset(_base.STATE_FIELDS|{'recovery_window_count','next_recovery_at_uptime','recovery_budget_pause'})
PHASES=frozenset(_base.PHASES|{'network-paused'})
REASONS=frozenset(_base.REASONS|{'link-recovery-pending','rolling-budget-wait'})


def parse_state(raw):
    """Explicitly incompatible with v1; no truncation of truthful counters."""
    if not isinstance(raw,bytes) or not 1<=len(raw)<=4096:raise ValueError('State bound')
    def pairs(items):
        value={}
        for key,item in items:
            if key in value:raise ValueError('Duplicate state key')
            value[key]=item
        return value
    value=json.loads(raw.decode('ascii'),object_pairs_hook=pairs)
    parent_module()  # Recheck the frozen source before accepting a status.
    if (not isinstance(value,dict) or set(value)!=STATE_FIELDS or value['kind']!=KIND
            or value['phase'] not in PHASES or value['reason'] not in REASONS
            or not isinstance(value['boot_id'],str)
            or not re.fullmatch(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}',value['boot_id'])):raise ValueError('State schema')
    for key in ('uptime_seconds','runner_pid','client_pid','observer_pid','attempt','recovery_used','observer_segment','recovery_window_count','next_recovery_at_uptime'):
        if type(value[key]) is not int or not 0<=value[key]<=2147483647:raise ValueError('Numeric state')
    if value['runner_pid']<1 or value['recovery_window_count']>2 or value['recovery_used']<value['recovery_window_count']:raise ValueError('Recovery counters')
    for key in ('eap_success_seen','failure_latched','recovery_budget_pause'):
        if type(value[key]) is not bool:raise ValueError('Boolean state')
    if value['wan_carrier'] is not None and (type(value['wan_carrier']) is not int or value['wan_carrier'] not in (0,1)):raise ValueError('Carrier state')
    if value['observer_exit_code'] is not None and (type(value['observer_exit_code']) is not int or not 0<=value['observer_exit_code']<=255):raise ValueError('Observer exit')
    return value


def build_runner(directory=DIRECTORY,minieap_sha=None,observer_sha=None):
    text=parent_module().build_runner(directory,minieap_sha,observer_sha).decode('ascii')
    text=change(text,'ATTEMPT=0; RECOVERY=0; OP_RC=null; NEXT_SAMPLE=0; AUTH_DEADLINE=0; SEGMENT=0',
        'ATTEMPT=0; RECOVERY=0; OP_RC=null; NEXT_SAMPLE=0; AUTH_DEADLINE=0; SEGMENT=0\n'
        'RECOVERY_PENDING=false; RECOVERY_TIMES=; LAST_CREDENTIAL=0; WINDOW_COUNT=0; NEXT_ELIGIBLE=0; RATE_PAUSED=false')
    text=change(text,'\ngate() {','\n'+BUDGET+'\ngate() {')
    text=change(text,'state() {\n carrier=',
        'state() {\n refresh_recovery_window || { latch supervisor-error; return 1; }\n carrier=')
    # Keep all original state fields, widen counters without resetting them, add
    # explicit window/deadline fields, and change kind so v1 readers fail closed.
    text=change(text,'"kind":"stock_campus_service_state_v1","phase":"%s"','"kind":"stock_campus_service_state_v2","phase":"%s"')
    text=change(text,'"observer_exit_code":%s}\\n\'','"observer_exit_code":%s,"recovery_window_count":%s,"next_recovery_at_uptime":%s,"recovery_budget_pause":%s}\\n\'')
    text=change(text,'"$SEGMENT" "$OP_RC" > "$R/state.json.new"',
        '"$SEGMENT" "$OP_RC" "$WINDOW_COUNT" "$NEXT_ELIGIBLE" "$RATE_PAUSED" > "$R/state.json.new"')
    text=change(text,' SUCCESS=false; PHASE=checking; REASON=checking-live-gate; state',
        ' SUCCESS=false; PHASE=checking; REASON=checking-live-gate; RATE_PAUSED=false; state')
    text=change(text,' # This explicit protocol action occurs at most once for this attempt.',
        ' # Require fresh consecutive samples after potentially slow live gates.\n'
        ' stable_carrier || { REASON=local-stop; return 1; }\n'
        ' # Reserve only after all live gates, before any recovery Logoff.\n'
        ' reserve_recovery || { latch supervisor-error; return 1; }\n'
        ' # This explicit protocol action occurs at most once for this attempt.')
    text=change(text,' ATTEMPT=$(( ATTEMPT+1 )); printf',
        ' test "$ATTEMPT" -lt 2147483647 || { latch supervisor-error; return 1; }\n'
        ' LAST_CREDENTIAL=$(now); RECOVERY_PENDING=false\n ATTEMPT=$(( ATTEMPT+1 )); printf')
    text=change(text,'    begin_attempt || exit 0',
        '    if ! recovery_ready; then\n'
        '     PHASE=network-paused; REASON=rolling-budget-wait; RATE_PAUSED=true; state\n'
        '     sleep 1; continue\n'
        '    fi\n'
        '    begin_attempt || exit 0')
    text=change(text,'    sleep 3\n    test "$(cat /sys/class/net/eth0.1/carrier 2>/dev/null || true)" = 1 || continue',
        '    stable_carrier || continue')
    text=change(text,
        '   if test "$RECOVERY" != 0 || test -e "$R/recovery.used"; then latch recovery-budget-exhausted; exit 0; fi\n'
        '   (set -C; printf \'1\\n\' > "$R/recovery.used")\n'
        '   RECOVERY=1; PHASE=waiting-wan; REASON=one-link-recovery-pending; state',
        '   # Close the small Failure-arrival race while the children stop.\n'
        '   if grep -q \'"direction":"in".*"eap_code":4,\' "$R/eap.current.jsonl"; then latch eap-failure; exit 0; fi\n'
        '   RECOVERY_PENDING=true; PHASE=waiting-wan; REASON=link-recovery-pending; state')
    text=change(text,'{"kind":"stock_campus_service_state_v1","phase":"not-running"}',
        '{"kind":"stock_campus_service_state_v2","phase":"not-running"}')
    return text.encode('ascii')


BUDGET=r'''# Pure policy helpers: no network, Logoff, child spawning, or fault clearing.
# Window timestamps describe recovery-workflow reservations, not EAP successes.
stable_carrier() {
 for stable_second in 1 2 3; do
  start_conditions || return 1
  sleep 1
 done
 start_conditions
}
refresh_recovery_window() {
 WINDOW_COUNT=0
 budget_now=$(now); kept=; oldest=0
 for stamp in $RECOVERY_TIMES; do
  case "$stamp" in ''|*[!0-9]*) return 1;; esac
  test "$stamp" -le "$budget_now" || return 1
  if test $(( budget_now-stamp )) -lt 1800; then
   kept="$kept $stamp"; WINDOW_COUNT=$(( WINDOW_COUNT+1 ))
   if test "$oldest" = 0; then oldest=$stamp; fi
  fi
 done
 RECOVERY_TIMES=$kept
}
recovery_ready() {
 RATE_PAUSED=false; NEXT_ELIGIBLE=0
 refresh_recovery_window || return 1
 test "$RECOVERY_PENDING" = true || return 0
 # Minimum 300 seconds after the last actual credential-process start.
 if test "$LAST_CREDENTIAL" -gt 0; then NEXT_ELIGIBLE=$(( LAST_CREDENTIAL+300 )); fi
 if test "$WINDOW_COUNT" -ge 2 && test $(( oldest+1800 )) -gt "$NEXT_ELIGIBLE"; then NEXT_ELIGIBLE=$(( oldest+1800 )); fi
 if test "$budget_now" -lt "$NEXT_ELIGIBLE"; then RATE_PAUSED=true; return 1; fi
 return 0
}
reserve_recovery() {
 test "$RECOVERY_PENDING" = true || return 0
 recovery_ready || return 1
 test "$WINDOW_COUNT" -lt 2 && test "$RECOVERY" -lt 2147483647 || return 1
 # RAM audit append before a Logoff. This file is never deleted/reset by policy.
 if test -e "$R/recovery.history" || test -L "$R/recovery.history"; then
  safe_file "$R/recovery.history" 600 && test "$(stat -c %s "$R/recovery.history")" -le 1048500 || return 1
 fi
 stamp=$(now); printf '%s\n' "$stamp" >> "$R/recovery.history" || return 1
 RECOVERY_TIMES="$RECOVERY_TIMES $stamp"; RECOVERY=$(( RECOVERY+1 )); WINDOW_COUNT=$(( WINDOW_COUNT+1 ))
 RATE_PAUSED=false; NEXT_ELIGIBLE=0
}
'''


if __name__=='__main__':print('Offline rolling-recovery v2 renderer only; no installation or device action.')
