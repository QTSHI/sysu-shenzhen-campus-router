"""Offline next-boot runner variant; leaves the frozen and running service alone."""
import hashlib
from pathlib import Path

BASE=Path(__file__).resolve().parent
OLD_SHA='123738851aaefb0f01d14559d817cb9c1729a5c1def9b8f9a26c20efa04d13fd'
LOGOFF_SHA='51a8fad5da83e95c618a3e2d2ed23db3c2d16f3ceed2b51599ad53f934224bca'
DIRECTORY='/data/usr/sysu-campus-auth/service'


def old_module():
    if hashlib.sha256((BASE/'stock_persistent_runner.py').read_bytes()).hexdigest()!=OLD_SHA:
        raise ValueError('Frozen base runner changed')
    import stock_persistent_runner
    return stock_persistent_runner


def parse_state(raw):return old_module().parse_state(raw)


def change(source,before,after):
    if source.count(before)!=1:raise ValueError('Frozen runner replacement shape changed')
    return source.replace(before,after,1)


def build_runner(directory=DIRECTORY,minieap_sha=None,observer_sha=None):
    source=old_module().build_runner(directory=directory,minieap_sha=minieap_sha,observer_sha=observer_sha).decode('ascii')
    source=change(source,
        ' test "$(hash "$D/minieap")" = "$MINISHA" && test "$(hash "$D/eapol-observer")" = "$OBSSHA"',
        ' safe_file "$D/logoff-once" 700 && safe_file "$D/logoff.sha256" 600 || return 1\n'
        ' test "$(cat "$D/logoff.sha256")" = "'+LOGOFF_SHA+'" && test "$(hash "$D/logoff-once")" = "'+LOGOFF_SHA+'" || return 1\n'
        ' test "$(hash "$D/minieap")" = "$MINISHA" && test "$(hash "$D/eapol-observer")" = "$OBSSHA"')
    source=change(source,'begin_attempt() {',READINESS+'\nbegin_attempt() {')
    source=change(source,
        ' valid_install && gate start || { latch start-gate-failed; return 1; }\n if ! observer;',
        ''' valid_install && gate start || { latch start-gate-failed; return 1; }
 # This explicit protocol action occurs at most once for this attempt.
 if ! start_conditions; then REASON=local-stop; return 1; fi
 (set -C; printf '1\\n' > "$R/logoff-attempt-$(( ATTEMPT+1 )).intent") || { latch start-gate-failed; return 1; }
 if ! "$D/logoff-once" --send-one-own-logoff </dev/null >/dev/null 2>&1; then latch start-gate-failed; return 1; fi
 for second in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25 26 27 28 29 30; do
  if ! start_conditions; then REASON=local-stop; return 1; fi
  sleep 1
 done
 if ! start_conditions; then REASON=local-stop; return 1; fi
 valid_install && gate start || { latch start-gate-failed; return 1; }
 if ! observer;''')
    source=change(source,
        ' if test -e "$R/stop.request" || test -L "$R/stop.request"; then exit 0; fi\n (set -C; printf',
        ' if test -e "$R/stop.request" || test -L "$R/stop.request"; then exit 0; fi\n'
        ' # No authentication, fault, boot intent, or runner lock during readiness.\n'
        ' if ! cold_boot_ready; then exit 0; fi\n (set -C; printf')
    return source.encode('ascii')


READINESS=r'''start_conditions() {
 enabled && test ! -e "$R/stop.request" && test ! -L "$R/stop.request" &&
 test ! -e "$D/fault" && test ! -L "$D/fault" &&
 test ! -e "$D/attempt.pending" && test ! -L "$D/attempt.pending" &&
 test "$(cat /sys/class/net/eth0.1/carrier 2>/dev/null || true)" = 1
}
cold_boot_ready() {
 ready_end=$(( $(now)+30 ))
 while start_conditions; do
  if test "$(now)" -ge "$ready_end"; then return 1; fi
  /usr/bin/lua "$D/gate.lua" start </dev/null >/dev/null 2>&1 &
  GP=$!
  while child_alive "$GP"; do
   if ! start_conditions || test "$(now)" -ge "$ready_end"; then
    stop_child "$GP" /usr/bin/lua; GP=; return 1
   fi
   sleep 1
  done
  ready_rc=0; wait "$GP" 2>/dev/null || ready_rc=$?; GP=
  if test "$ready_rc" = 0 && start_conditions; then return 0; fi
  if test "$(now)" -ge "$ready_end"; then return 1; fi
  sleep 1
 done
 return 1
}'''


if __name__=='__main__':print('Offline next-boot Logoff runner renderer; no device action.')
