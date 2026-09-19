#
# Login to "Dynamic DNS" page of afraid.org
#
# (c) 2024 Ingo Heinrich
# See LICENSE file for full license.
#

import logging
import os
import platform
import sys
from argparse import Namespace

import mechanicalsoup
import requests
from configargparse import ArgumentParser  # type: ignore

_LOG_FORMAT = "%(asctime)s | %(levelname)s | %(message)s"
_LOG_DATEFMT = "%Y-%m-%d %H:%M:%S"

logging.basicConfig(force=True, level=logging.WARNING, format=_LOG_FORMAT, datefmt=_LOG_DATEFMT)
_LOG = logging.getLogger(__name__)


def die(msg: str | None = None, *args, **kwargs):
    """
    End with CRITICAL log message

    :param msg: message to log, if None then no message is logged
    :param args: arguments for message formatting
    :param kwargs: keyword arguments for message formatting
    """
    if msg:
        _LOG.critical(msg, *args, **kwargs)
    sys.exit(1)


def init_args(argv: list | None = None) -> Namespace:
    """
    Configure and process command line arguments

    :param argv: optional list of arguments to parse, if None then sys.argv is used

    :return: parsed arguments as Namespace object
    """
    global _LOG
    # use platform to determine default config location
    system = platform.system()
    if system == "Linux":
        configs = [
            "/etc/login_afraid_org/default.conf",
            os.environ.get("XDG_CONFIG_HOME", "~/.config") + "/login_afraid_org/default.conf",
        ]
    elif system == "Windows":
        configs = [os.environ.get("LOCALAPPDATA", "~/AppData/Local") + "/login_afraid_org/default.conf"]
    elif system == "Darwin":
        configs = ["~/Library/Preferences/login_afraid_org/default.conf"]
    else:
        _LOG.warning('unknown platform: "%s", no default config paths available', system)
    # create parser
    parser = ArgumentParser(
        default_config_files=configs,
        ignore_unknown_config_file_keys=True,
        auto_env_var_prefix="LAO_",
        add_config_file_help=False,
        add_env_var_help=False,
        add_help=True,
        allow_abbrev=True,
        description="Login to afraid.org Dynamic DNS v2 page.",
        epilog=f'Options that start with "--" can also be set in a config file ({" or ".join(configs)} or specified '
        + "via -c). Config file syntax allows key=value (username=myusername or quiet=true or verbose=2) and domain="
        + "[a.afraid.org,b.afraid.org,c.afraid.org]. In general, command-line values override environment variables "
        + "which override values from configuration file.",
    )
    parser.add("-u", "--username", required=True, help="user for login to afraid.org [env var: LAO_USERNAME]")  # type: ignore
    parser.add("-p", "--password", required=True, help="password for login to afraid.org [env var: LAO_PASSWORD]")  # type: ignore
    parser.add(  # type: ignore
        "-d",
        "--domain",
        action="append",
        default=None,
        help="optional domain name registered for Dynamic DNS at afraid.org, only used to check if login was successful"
        + ', use multiple times to specify different domain names "-d a.afraid.org -d b.afraid.org -d c.afraid.org"'
        + " [env var: LAO_DOMAIN]",
    )
    parser.add("-c", "--config", is_config_file=True, help="optional path to config file")  # type: ignore
    parser.add(  # type: ignore
        "-q",
        "--quiet",
        action="store_true",
        default=False,
        help="no output, not even errors, check exit code for success or failure",
    )
    parser.add(  # type: ignore
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="show informational messages, use twice to also show debug messages, default: show errors and warnings"
        + " only",
    )

    # parse args
    args = parser.parse_args(args=argv)

    # (re-)configure logging
    level = logging.WARNING
    if args.quiet:
        # disable all log output
        level = logging.CRITICAL + 1
    elif args.verbose > 1:
        level = logging.DEBUG
    elif args.verbose > 0:
        level = logging.INFO
    if level != logging.WARNING:
        logging.basicConfig(force=True, level=level, format=_LOG_FORMAT, datefmt=_LOG_DATEFMT)
        _LOG = logging.getLogger(__name__)

    return args


def login(username: str, password: str, domains: list | None = None) -> None:
    """
    Log in to afraid.org with username and password, assert login worked then log out again.

    :param username: username for login
    :param password: password for login
    :param domains: optional list of domain names to check if they are listed in the page
    """
    log_is_debug = _LOG.level <= logging.DEBUG

    browser = None
    logout = False
    try:
        # setup browser: set user agent from a real browser (Firefox on Windows 10)
        browser = mechanicalsoup.StatefulBrowser(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
            + "Chrome/58.0.3029.110 Safari/537.3"
        )

        # open Dynamic DNS v2 page
        response: requests.Response | None = browser.open("https://freedns.afraid.org/dynamic/v2/")
        if not response or response.status_code != 200:
            die(
                "loading afraid.org Dynamic DNS v2 page failed%s",
                f" with HTTP code {response.status_code}" if response else "",
            )
        _LOG.debug("afraid.org Dynamic DNS v2 page loaded:\n----------\n%s\n----------", response.text)

        # fill and submit login form
        browser.select_form('form[action="/zc.php?step=2"]')
        browser["username"] = username
        browser["password"] = password
        response = browser.submit_selected(btnName="submit")
        if not response or not browser.page or response.status_code != 200 or not response.text:
            die(
                "failed login to afraid.org Dynamic DNS v2%s%s",
                f" with HTTP code {response.status_code}" if response else "",
                f":\n----------\n{response.text}\n----------" if log_is_debug and response and response.text else "",
            )
        logout = True
        _LOG.debug("afraid.org Dynamic DNS v2 after login:\n----------\n%s\n----------", response.text)

        # check if credentials were wrong in response content
        if "Invalid UserID/Pass" in response.text:
            die("afraid.org Dynamic DNS v2 login failed: invalid UserID/Pass")

        # validate login by asserting "|UserID:|<username>|" is in response content
        euserid = browser.page.find("td", string="UserID:")  # type: ignore
        if (
            not euserid
            or not (eusername := euserid.find_next_sibling("td"))
            or not eusername.text
            or eusername.text.strip() != username
        ):
            die('afraid.org Dynamic DNS v2 login failed, missing username "%s" in page', username)

        # optionally: check that all domains are listed
        if domains and (
            missing := set(domains) - {domain for domain in domains if browser.page.find("a", string=domain)}  # type: ignore
        ):
            die(
                'afraid.org Dynamic DNS v2 login failed, missing %s "%s" in page%s',
                "domain" if len(missing) == 1 else "domains",
                '" and "'.join(missing),
                f":\n----------\n{response.text}\n----------" if log_is_debug else "",
            )

        # inform user
        _LOG.info("afraid.org Dynamic DNS v2 login successful")

    except Exception as e:  # noqa: BLE001  # catch-all for unexpected errors
        die("afraid.org Dynamic DNS v2 login failed due to unexpected exception: %s", e, exc_info=e)
    finally:
        # logout + close
        if browser:
            try:
                if logout and (link := browser.find_link(text="Logout")):
                    response = browser.follow_link(link)
                    _LOG.debug(
                        "afraid.org Dynamic DNS v2 logout successful:\n----------\n%s\n----------", response.text
                    )
            except Exception as e:  # noqa: BLE001  # catch-all for unexpected errors
                _LOG.warning("afraid.org Dynamic DNS v2 logout failed: %s", e, exc_info=e if log_is_debug else None)
            finally:
                browser.close()


def main(argv: list | None = None) -> None:
    args = init_args(argv)
    login(args.username, args.password, args.domain)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # noqa: BLE001  # catch-all for unexpected errors
        die("unexpected failure: %s", e, exc_info=e)
