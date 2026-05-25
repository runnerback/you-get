#!/usr/bin/env python

import getopt
import os
import platform
import sys

# 优先加载 .env：APP_ENV=production 时读 .env.production，否则读 .env
# shell 已有的环境变量优先级最高（override=False）
try:
    from dotenv import load_dotenv

    _env_name = os.getenv("APP_ENV", "development")
    _env_file = ".env.production" if _env_name == "production" else ".env"
    # 项目根目录（向上 3 层：__main__.py -> you_get/ -> src/ -> 项目根）
    _project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    _env_path = os.path.join(_project_root, _env_file)
    if os.path.exists(_env_path):
        load_dotenv(_env_path, override=False)
except ImportError:
    pass  # 没装 python-dotenv 也能跑（CLI 静默降级）

from .version import script_name, __version__
from .util import git, log

_options = [
    'help',
    'version',
    'gui',
    'force',
    'playlists',
]
_short_options = 'hVgfl'

_help = """Usage: {} [OPTION]... [URL]...
TODO
""".format(script_name)

# TBD
def main_dev(**kwargs):
    """Main entry point.
    you-get-dev
    """

    # Get (branch, commit) if running from a git repo.
    head = git.get_head(kwargs['repo_path'])

    # Get options and arguments.
    try:
        opts, args = getopt.getopt(sys.argv[1:], _short_options, _options)
    except getopt.GetoptError as e:
        log.wtf("""
    [Fatal] {}.
    Try '{} --help' for more options.""".format(e, script_name))

    if not opts and not args:
        # Display help.
        print(_help)
        # Enter GUI mode.
        #from .gui import gui_main
        #gui_main()
    else:
        conf = {}
        for opt, arg in opts:
            if opt in ('-h', '--help'):
                # Display help.
                print(_help)

            elif opt in ('-V', '--version'):
                # Display version.
                log.println("you-get:", log.BOLD)
                log.println("    version:  {}".format(__version__))
                if head is not None:
                    log.println("    branch:   {}\n    commit:   {}".format(*head))
                else:
                    log.println("    branch:   {}\n    commit:   {}".format("(stable)", "(tag v{})".format(__version__)))

                log.println("    platform: {}".format(platform.platform()))
                log.println("    python:   {}".format(sys.version.split('\n')[0]))

            elif opt in ('-g', '--gui'):
                # Run using GUI.
                conf['gui'] = True

            elif opt in ('-f', '--force'):
                # Force download.
                conf['force'] = True

            elif opt in ('-l', '--playlist', '--playlists'):
                # Download playlist whenever possible.
                conf['playlist'] = True

        if args:
            if 'gui' in conf and conf['gui']:
                # Enter GUI mode.
                from .gui import gui_main
                gui_main(*args, **conf)
            else:
                # Enter console mode.
                from .console import console_main
                console_main(*args, **conf)

def main(**kwargs):
    """Main entry point.
    you-get (legacy)
    """
    from .common import main
    main(**kwargs)

if __name__ == '__main__':
    main()
