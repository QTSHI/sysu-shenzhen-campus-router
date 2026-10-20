#!/usr/bin/env python3
"""Render reviewed shell text offline. No installation, network or authentication."""
# SPDX-License-Identifier: GPL-3.0-only
import argparse
import hashlib
import importlib
import json
from pathlib import Path
import re
import sys

BASE=Path(__file__).resolve().parent
SOURCE_SHA256={
    'stock_persistent_runner.py':'123738851aaefb0f01d14559d817cb9c1729a5c1def9b8f9a26c20efa04d13fd',
    'stock_persistent_runner_logoff.py':'502aabcd2fc7a87c1a4ed76a257282add7cc828819c2128ad32e8259a85f2e44',
    'stock_persistent_runner_shutdown.py':'9a4030a341559633e6374381cbdb78447590de402719e9396d84c9a4c9ed0808',
    'stock_persistent_runner_rolling_candidate.py':'0fddb2f34521a6b9104a5f917d2958fb1283c148130df9fbb15457f1f0098fc6',
}


def verify_sources():
    """Check all four exact copies before importing the hash-linked renderers."""
    for name,expected in SOURCE_SHA256.items():
        path=BASE/name
        if not path.is_file()or path.is_symlink()or hashlib.sha256(path.read_bytes()).hexdigest()!=expected:
            raise ValueError('Reviewed renderer source changed')
    return dict(SOURCE_SHA256)


def renderer():
    verify_sources()
    if str(BASE)not in sys.path:sys.path.insert(0,str(BASE))
    for name in SOURCE_SHA256:
        loaded=sys.modules.get(name[:-3])
        if loaded is not None and Path(getattr(loaded,'__file__','')).resolve()!=BASE/name:
            raise ValueError('Renderer import scope changed')
    return importlib.import_module('stock_persistent_runner_rolling_candidate')


def digest(value):
    if not isinstance(value,str)or not re.fullmatch('[0-9a-f]{64}',value):
        raise argparse.ArgumentTypeError('Use exactly 64 lowercase hexadecimal characters')
    return value


def render(artifact,minieap_sha256,observer_sha256):
    """Return ASCII shell source only; never execute the generated text."""
    digest(minieap_sha256);digest(observer_sha256)
    module=renderer()
    if artifact=='runner':
        result=module.build_runner(minieap_sha=minieap_sha256,observer_sha=observer_sha256)
    elif artifact=='shutdown':
        result=module.parent_module().build_shutdown(minieap_sha=minieap_sha256,observer_sha=observer_sha256)
    else:raise ValueError('Choose runner or shutdown')
    if not isinstance(result,bytes)or not result.startswith(b'#!/bin/sh\n')or b'@MINI@'in result or b'@OBS@'in result:
        raise ValueError('Rendered source shape changed')
    result.decode('ascii','strict')
    return result


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--render',action='store_true',help='Explicitly generate shell source; never run it')
    parser.add_argument('--artifact',choices=('runner','shutdown'))
    parser.add_argument('--minieap-sha256',type=digest)
    parser.add_argument('--observer-sha256',type=digest)
    parser.add_argument('--output',type=Path,help='New file only; omit to write source to stdout')
    args=parser.parse_args(argv)
    if not args.render:
        if any((args.artifact,args.minieap_sha256,args.observer_sha256,args.output)):
            parser.error('Add --render to generate source')
        parser.print_help();return 0
    if not all((args.artifact,args.minieap_sha256,args.observer_sha256)):
        parser.error('--artifact and both pinned binary digests are required')
    try:
        data=render(args.artifact,args.minieap_sha256,args.observer_sha256)
        if args.output is None:
            sys.stdout.buffer.write(data)
        else:
            with args.output.open('xb')as stream:stream.write(data)
            print(json.dumps({'artifact':args.artifact,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()},sort_keys=True))
        return 0
    except (ValueError,OSError):
        print('Offline rendering stopped; verify source hashes and choose a new output file.',file=sys.stderr)
        return 2


if __name__=='__main__':raise SystemExit(main())
