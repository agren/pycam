#!/usr/bin/env python3
"""

Copyright 2017 Lars Kruse <devel@sumpfralle.de>

This file is part of PyCAM.

PyCAM is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

PyCAM is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with PyCAM.  If not, see <http://www.gnu.org/licenses/>.
"""

import argparse
import logging
import os
import sys

# we need the multiprocessing exception for remote connections
try:
    import multiprocessing
    from multiprocessing import AuthenticationError
except ImportError:
    multiprocessing = None
    # use an arbitrary other Exception
    AuthenticationError = socket.error

try:
    from pycam import VERSION
except ImportError:
    # running locally (without a proper PYTHONPATH) requires manual intervention
    sys.path.insert(0, os.path.realpath(os.path.join(os.path.dirname(os.path.realpath(__file__)),
                                                     os.pardir)))
    from pycam import VERSION

import pycam.errors
from pycam.Flow.parser import parse_yaml
import pycam.Utils
import pycam.Utils.log
import pycam.workspace.data_models


_log = pycam.Utils.log.get_logger()

LOG_LEVELS = {"debug": logging.DEBUG,
              "info": logging.INFO,
              "warning": logging.WARNING,
              "error": logging.ERROR, }

EXIT_CODES = {"ok": 0,
              "server_without_password": 5,
              "connection_error": 6
              }


def get_args():
    parser = argparse.ArgumentParser(prog="PyCAM", description="scriptable PyCAM processing flow",
                                     epilog="PyCAM website: https://github.com/SebKuzminsky/pycam")
    # general options
    group_processing = parser.add_argument_group("Processing")
    group_processing.add_argument(
        "--number-of-processes", dest="parallel_processes", default=None, type=int,
        action="store",
        help=("override the default detection of multiple CPU cores. Parallel processing only "
              "works with Python 2.6 (or later) or with the additional 'multiprocessing' module."))
    group_processing.add_argument(
        "--enable-server", dest="enable_server", default=False, action="store_true",
        help="enable a local server and (optionally) remote worker servers.")
    group_processing.add_argument(
        "--remote-server", dest="remote_server", default=None, action="store",
        help=("Connect to a remote task server to distribute the processing load. "
              "The server is given as an IP or a hostname with an optional port (default: 1250) "
              "separated by a colon."))
    group_processing.add_argument(
        "--start-server-only", dest="start_server", default=False, action="store_true",
        help="Start only a local server for handling remote requests.")
    group_processing.add_argument(
        "--server-auth-key", dest="server_authkey", default="", action="store",
        help=("Secret used for connecting to a remote server or for granting access to remote "
              "clients."))
    parser.add_argument("--log-level", choices=LOG_LEVELS.keys(), default="warning",
                        help="choose the verbosity of log messages")
    parser.add_argument("sources", metavar="FLOW_SPEC", type=argparse.FileType('r'), nargs="+",
                        help="processing flow description files in yaml format")
    parser.add_argument("--version", action="version", version="%(prog)s {}".format(VERSION))
    return parser.parse_args()


def main_func():
    args = get_args()
    _log.setLevel(LOG_LEVELS[args.log_level])
    for fname in args.sources:
        try:
            parse_yaml(fname)
        except pycam.errors.PycamBaseException as exc:
            print("Flow description parse failure ({}): {}".format(fname, exc), file=sys.stderr)
            sys.exit(1)
    pycam.Utils.set_application_key("pycam-cli")

    # check if server-auth-key is given -> this is mandatory for server mode
    if (args.enable_server or args.start_server) and not args.server_authkey:
        parser.error(
            "You need to supply a shared secret for server mode. This is supposed to prevent you "
            "from exposing your host to remote access without authentication.\nPlease add the "
            "'--server-auth-key' argument followed by a shared secret password.")
        return EXIT_CODES["server_without_password"]
    
    # initialize multiprocessing
    try:
        if args.server_authkey is None:
            server_auth_key = None
        else:
            server_auth_key = args.server_authkey.encode("utf-8")
        if args.start_server:
            pycam.Utils.threading.init_threading(
                args.parallel_processes, remote=args.remote_server, run_server=True,
                server_credentials=server_auth_key)
            pycam.Utils.threading.cleanup()
            return EXIT_CODES["ok"]
        else:
            pycam.Utils.threading.init_threading(
                args.parallel_processes, enable_server=args.enable_server,
                remote=args.remote_server, server_credentials=server_auth_key)
    except socket.error as err_msg:
        log.error("Failed to connect to remote server: %s", err_msg)
        return EXIT_CODES["connection_error"]
    except AuthenticationError as err_msg:
        log.error("The remote server rejected your authentication key: %s", err_msg)
        return EXIT_CODES["connection_error"]

    for export in pycam.workspace.data_models.Export.get_collection():
        export.run_export()


if __name__ == "__main__":
    main_func()
