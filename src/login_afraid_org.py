#
# Login to "Dynamic DNS" page of afraid.org
#
# (c) 2024 Ingo Heinrich
# See LICENSE file for full license.
#

import logging
import os
import platform
import re
import sys
from argparse import Namespace

import mechanize
from configargparse import ArgumentParser  # type: ignore


def die(msg: str | None = None, *args, **kwargs):
    """End with CRITICAL log message"""
    if msg:
        logging.critical(msg, *args, **kwargs)
    sys.exit(1)


def init_args(argv: list = None) -> Namespace:
    """Configure and process command line arguments"""
    system = platform.system()
    if system == "Linux":
        configs = [
            "/etc/login_afraid_org/default.conf",
            os.environ.get("XDG_CONFIG_HOME", "~/.config") + "/login_afraid_org/default.conf",
        ]
    elif system == "Windows":
        configs = [os.environ.get("LOCALAPPDATA") + "/login_afraid_org/default.conf"]
    elif system == "Darwin":
        configs = ["~/Library/Preferences/login_afraid_org/default.conf"]
    else:
        logging.warning('unknown platform: "%s", no default config paths available', system)
    parser = ArgumentParser(
        default_config_files=configs,
        ignore_unknown_config_file_keys=True,
        auto_env_var_prefix="LAO_",
        add_config_file_help=False,
        add_env_var_help=False,
        add_help=True,
        allow_abbrev=True,
        description="Login to afraid.org Dynamic DNS service to prevent account expiry.",
        epilog=f'Options that start with "--" can also be set in a config file ({" or ".join(configs)} or specified via'
        + " -c). Config file syntax allows: key=value (username=myusername or quiet=true or verbose=2), domain="
        + "[a.afraid.org,b.afraid.org,c.afraid.org]. In general, command-line values override environment variables"
        + " which override defaults.",
    )
    parser.add("-u", "--username", required=True, help="user for login to afraid.org [env var: LAO_USERNAME]")
    parser.add("-p", "--password", required=True, help="password for login to afraid.org [env var: LAO_PASSWORD]")
    parser.add(
        "-d",
        "--domain",
        action="append",
        default=None,
        help="optional domain name registered for Dynamic DNS at afraid.org, only used to check if login was successful"
        + ', use multiple times to specify different domain names "-d a.afraid.org -d b.afraid.org -d c.afraid.org"'
        + " [env var: LAO_DOMAIN]",
    )
    parser.add("-c", "--config", is_config_file=True, help="optional path to config file")
    parser.add(
        "-q",
        "--quiet",
        action="store_true",
        default=False,
        help="no output, not even errors, check exit code for success or failure",
    )
    parser.add(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="show informational messages, use twice to also show debug messages, default: show errors and warnings"
        + " only",
    )

    args = parser.parse_args(args=argv)
    if args.quiet:
        # disable all log output
        logging.basicConfig(level=logging.CRITICAL + 1)
    elif args.verbose > 1:
        logging.basicConfig(level=logging.DEBUG)
    elif args.verbose > 0:
        logging.basicConfig(level=logging.INFO)
    else:
        # default >= WARNING
        logging.basicConfig(level=logging.WARNING)
    formatter = logging.Formatter("%(asctime)s|%(levelname)s|%(message)s", "%Y-%m-%d %H:%M:%S")
    for handler in logging.getLogger("root").handlers:
        handler.setFormatter(formatter)

    return args


def login(username: str, password: str, domains: list | None = None):
    """Log in to afraid.org with username and password, assert login worked then log out again."""
    log = logging.getLogger()

    browser = mechanize.Browser()

    # pretend we are not a robot ...
    browser.set_handle_robots(False)

    # set user agent to make it look like a real browser
    browser.addheaders = [
        (
            "User-agent",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110"
            + " Safari/537.3",
        )
    ]

    # navigate to login page
    response = browser.open("https://freedns.afraid.org/dynamic/")
    if response.code != 200:
        die("loading afraid.org Dynamic DNS page failed with HTTP code %s", response.code)
    log.debug("afraid.org Dynamic DNS page loaded: %s", response)

    # get login form
    forms = browser.forms()
    loginform: mechanize.HTMLForm = None
    for form in forms:
        if form.action.find("/zc.php") > -1:
            loginform = form
    if not loginform:
        die("login form not found")
    log.debug("login form: %s", loginform)

    # get login button
    login: mechanize.SubmitControl = None
    for control in loginform.controls:
        if control.name == "submit" and control.value.lower() == "login":
            login = control
            break
    if not login:
        die("login button not found")
    log.debug("login button: %s", login)

    # fill username and password
    loginform["username"] = username
    loginform["password"] = password

    # submit using login button
    response = browser.open(loginform.click(id=login.id))
    if response.code != 200:
        die("login failed with HTTP code %s", response.code)
    log.debug("login done: %s", response)

    # check response content - since response code is basically always "200 - OK"
    result = response.read().decode()
    match_user = re.compile(r"<tr>\s*<td[^>]*>\s*UserID:</td>\s*<td[^>]*>" + username + r"\s*</td>\s*</tr>").search(
        result
    )
    if not match_user:
        die(f'login failed - username "{username}" not found in response')
    if domains:
        for domain in domains:
            if result.find(domain) == -1:
                die(f'login failed - domain "{domain}" not found in response')
    log.info("login successful")

    # logout
    try:
        link = browser.find_link(text="Logout")
        if link:
            log.debug("logout link: %s", link)
            response = browser.follow_link(link)
            log.debug("logout successful: %s", response)
        else:
            log.warning("logout link not found")
    except Exception as e:
        if log.isEnabledFor(logging.DEBUG):
            log.warning("logout failed: %s", e, exc_info=True)
        else:
            log.warning("logout failed")


if __name__ == "__main__":
    try:
        args = init_args(sys.argv[1:])
        login(args.username, args.password, args.domain)
    except Exception as e:
        if logging.getLogger().isEnabledFor(logging.DEBUG):
            die("unexpected failure: %s", e, exc_info=True)
        else:
            die("unexpected failure: %s", e)
        
