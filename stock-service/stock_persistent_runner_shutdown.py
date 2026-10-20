"""Offline orderly-shutdown candidate; never installs or contacts the router.

The frozen Logoff renderer remains untouched.  The K hook must be installed
before a service is enabled and its actual ordering must be verified on stock.
"""
import hashlib
from pathlib import Path

BASE = Path(__file__).resolve().parent
PARENT_SHA = '502aabcd2fc7a87c1a4ed76a257282add7cc828819c2128ad32e8259a85f2e44'
DIRECTORY = '/data/usr/sysu-campus-auth/service'
HOOK = '/etc/rc.d/K01sysu-campus-auth'


def parent_module():
    if hashlib.sha256((BASE / 'stock_persistent_runner_logoff.py').read_bytes()).hexdigest() != PARENT_SHA:
        raise ValueError('Frozen Logoff renderer changed')
    import stock_persistent_runner_logoff
    return stock_persistent_runner_logoff


def parse_state(raw):
    return parent_module().parse_state(raw)


def change(source, before, after):
    if source.count(before) != 1:
        raise ValueError('Frozen runner replacement shape changed')
    return source.replace(before, after, 1)


def build_shutdown(directory=DIRECTORY, minieap_sha=None, observer_sha=None):
    source = parent_module().build_runner(directory=directory, minieap_sha=minieap_sha,
                                         observer_sha=observer_sha).decode('ascii')
    # Only the already reviewed root/file/process checks, not its command switch.
    prefix = source[:source.index('\ngate() {')]
    return (prefix + '\n' + SHUTDOWN).encode('ascii')


def build_runner(directory=DIRECTORY, minieap_sha=None, observer_sha=None):
    source = parent_module().build_runner(directory=directory, minieap_sha=minieap_sha,
                                         observer_sha=observer_sha).decode('ascii')
    digest = hashlib.sha256(build_shutdown(directory, minieap_sha, observer_sha)).hexdigest()
    source = change(source,
        ' test "$(hash "$D/minieap")" = "$MINISHA" && test "$(hash "$D/eapol-observer")" = "$OBSSHA"',
        ' safe_file "$D/shutdown.sh" 700 && safe_file "$D/shutdown.sha256" 600 || return 1\n'
        ' test "$(cat "$D/shutdown.sha256")" = "' + digest + '" && test "$(hash "$D/shutdown.sh")" = "' + digest + '" || return 1\n'
        ' test "$(hash "$D/minieap")" = "$MINISHA" && test "$(hash "$D/eapol-observer")" = "$OBSSHA"')
    source = change(source, '\ncase "${1:-}" in', '\n' + INSTALL_HOOK + '\ncase "${1:-}" in')
    source = change(source, 'ensure)\n valid_install || exit 20',
                    'ensure)\n valid_install && install_shutdown_hook || exit 20')
    source = change(source, 'run)\n valid_install && enabled && runtime || exit 20',
        'run)\n valid_install && enabled && runtime || exit 20\n'
        ' # An ensure child may have forked immediately before the K hook locked it.\n'
        ' if test -e "$R/stop.request" || test -L "$R/stop.request"; then exit 0; fi')
    old_failure = '   if grep -q \'"direction":"in".*"eap_code":4,\' "$R/eap.current.jsonl"; then latch eap-failure; exit 0; fi\n'
    source = change(source, old_failure, '')
    source = change(source,
        '  carrier=$(cat /sys/class/net/eth0.1/carrier 2>/dev/null || true)\n'
        '  case "$carrier" in 0|1) :;; *) latch carrier-unavailable; exit 0;; esac',
        '  # A real received Failure takes priority over ordinary link loss.\n'
        '  if test -n "$CP" && grep -q \'"direction":"in".*"eap_code":4,\' "$R/eap.current.jsonl"; then latch eap-failure; exit 0; fi\n'
        '  carrier=$(cat /sys/class/net/eth0.1/carrier 2>/dev/null || true)\n'
        '  case "$carrier" in 0|1) :;; *)\n'
        '   if test "$SUCCESS" = true && test ! -e "$D/attempt.pending" && test ! -L "$D/attempt.pending"; then\n'
        '    # An administratively down netdev reports unreadable carrier.  A\n'
        '    # previously proven session uses the same one-recovery link path.\n'
        '    carrier=0\n'
        '   else latch carrier-unavailable; exit 0; fi;;\n'
        '  esac')
    return source.encode('ascii')


INSTALL_HOOK = r'''install_shutdown_hook() {
 # The current stock overlay has a real root-owned 0755 rc.d directory.
 test -d /etc/rc.d && test ! -L /etc/rc.d || return 1
 test "$(stat -c '%u:%a' /etc/rc.d)" = '0:755' || return 1
 hook=/etc/rc.d/K01sysu-campus-auth
 if test -L "$hook"; then
  test "$(stat -c %u "$hook")" = 0 && test "$(readlink "$hook")" = "$D/shutdown.sh"
 elif test -e "$hook"; then return 1
 else
  ln -s "$D/shutdown.sh" "$hook" || return 1
  test -L "$hook" && test "$(stat -c %u "$hook")" = 0 && test "$(readlink "$hook")" = "$D/shutdown.sh"
 fi
}'''


SHUTDOWN = r'''# Only the stock K callback may request this path; no authentication here.
test "${1:-}" = shutdown || exit 2
valid_install && runtime || exit 20
safe_file "$D/shutdown.sh" 700 && safe_file "$D/shutdown.sha256" 600 || exit 20
test "$(hash "$D/shutdown.sh")" = "$(cat "$D/shutdown.sha256")" || exit 20
# Keep cron/any already forked run child from starting credentials.
if test ! -e "$R/stop.request" && test ! -L "$R/stop.request"; then
 (set -C; : > "$R/stop.request") || exit 21
fi
safe_file "$R/stop.request" 600 || exit 21
(set -C; printf '%s\n' "$(boot)" > "$R/shutdown.intent") 2>/dev/null || exit 0
safe_file "$R/shutdown.intent" 600 || exit 21
LOCKED=false
trap 'if test "$LOCKED" = true; then rmdir "$R/ensure.lock" 2>/dev/null || true; fi' EXIT
lock_end=$(( $(now)+1 ))
until mkdir -m 700 "$R/ensure.lock" 2>/dev/null; do
 test "$(now)" -lt "$lock_end" || exit 0
 sleep 1
done
LOCKED=true
clean_session=false
had_runner=false
if own_runner; then
 had_runner=true
 RP=$rp; RT=$rt
 # The only state used for logout eligibility is a current verified session.
 if safe_file "$R/state.json" 600 && test "$(stat -c %s "$R/state.json")" -le 2048 &&
    test ! -e "$D/fault" && test ! -L "$D/fault" &&
    test ! -e "$D/attempt.pending" && test ! -L "$D/attempt.pending" &&
    grep -Fq '"boot_id":"'"$(boot)"'"' "$R/state.json" &&
    grep -Fq '"eap_success_seen":true,"failure_latched":false,' "$R/state.json"; then
  cp=$(sed -n 's/.*"client_pid":\([0-9][0-9]*\),.*/\1/p' "$R/state.json")
  case "$cp" in ''|0|*[!0-9]*) :;; *)
   if test "$(readlink /proc/$cp/exe 2>/dev/null || true)" = "$D/minieap" &&
      awk -v owner="$rp" '$1=="PPid:" && $2==owner {ok=1} END {exit !ok}' "/proc/$cp/status" 2>/dev/null; then clean_session=true; fi;;
  esac
 fi
 # Immediate verified signal, rather than the 10-second interactive stop path.
 own_runner && test "$rp" = "$RP" && test "$rt" = "$RT" || exit 0
 kill -TERM "$rp" 2>/dev/null || true
fi
service_children_absent() {
 for proc in /proc/[0-9]*/exe; do
  exe=$(readlink "$proc" 2>/dev/null || true)
  case "$exe" in */minieap|*/minieap\ \(deleted\)|*/eapol-observer|*/eapol-observer\ \(deleted\)) return 1;; esac
 done
 return 0
}
runner_gone() {
 test "$had_runner" = true || return 0
 test "$(start_tick "$rp")" = "$rt" || return 0
 # A zombie cannot send, fork, or retain an authentication child.
 awk '$1=="State:" && $2=="Z" {z=1} END {exit !z}' "/proc/$rp/status" 2>/dev/null
}
stop_end=$(( $(now)+3 ))
while ! runner_gone || ! service_children_absent; do
 test "$(now)" -lt "$stop_end" || exit 0
 sleep 1
done
# No deliberate Logoff has been sent, so an already observed Failure is real.
safe_file "$R/eap.current.jsonl" 600 || exit 0
test "$(stat -c %s "$R/eap.current.jsonl")" -le 262144 || exit 0
metadata_rc=0
awk '
 BEGIN {n="[0-9]+";v="(null|[0-9]+)";
 p="^\\{\"seq\":"n",\"elapsed_ms\":"n",\"direction\":\"(in|out)\",\"wire_length\":"n",\"eapol_version\":"n",\"eapol_type\":"n",\"eapol_body_length\":"n",\"eap_code\":"v",\"eap_id\":"v",\"eap_length\":"v",\"eap_type\":"v"\\}$"}
 $0 !~ p {bad=1;next}
 /"direction":"in".*"eap_code":4,/ {failure=1}
 END {if(failure)exit 42;if(bad)exit 43}
' "$R/eap.current.jsonl" || metadata_rc=$?
if test "$metadata_rc" = 42; then latch eap-failure; exit 0; fi
test "$metadata_rc" = 0 && test "$clean_session" = true || exit 0
test ! -e "$D/fault" && test ! -L "$D/fault" || exit 0
test ! -e "$D/attempt.pending" && test ! -L "$D/attempt.pending" || exit 0
runner_gone && service_children_absent || exit 0
# Fixed tool checks own MAC/interface and carrier, sends at most one frame,
# and has an internal five-second alarm.  There is no retry or credential read.
"$D/logoff-once" --send-one-own-logoff </dev/null >/dev/null 2>&1 || exit 0
exit 0
'''


if __name__ == '__main__':
    print('Offline orderly-shutdown renderer; no device action or fault clearing.')
