#!/bin/bash
#
# Setup environment to develop and/or execute login_afraid_org.
#
# (c) 2024 Ingo Heinrich
# See LICENSE file for full license.
#

set -o pipefail

function die() {
    [[ -z ${*} ]] || echo "[CRITICAL] $*" >&2
    exit 1
}

[[ $(id -u) -ne 0 ]] || die "do not execute ${0} as root"

function help() {
    if [[ -z ${INSTALL_DIR} ]]; then
        cd "$(dirname "${0}")" || die "failed to change to $(dirname "${0}")"
        INSTALL_DIR="$(pwd)"
        export INSTALL_DIR
    fi
    if [[ ! -e "${INSTALL_DIR}/activate" ]]; then
        echo "syntax: ${0}"
        echo
        echo "Execute ${0} without arguments to setup login_afraid_org environment."
    else
        [[ -n ${RUN_DIR} ]] || RUN_DIR="$(dirname "${INSTALL_DIR}")"
        echo "Always activate environment: source '${INSTALL_DIR}/activate'"
        echo "To execute as script: cd '${RUN_DIR}' && pdm run python src/login_afraid_org.py"
        echo "To create a standalone binary: cd '${RUN_DIR}' && pdm run pyinstaller --clean dev/login_afraid_org.spec"
        echo "Then to execute standalone binary: '${RUN_DIR}/dist/login_afraid_org'"
        echo "To deactivate environment: source '${INSTALL_DIR}/deactivate'"
        echo
        echo "To permanently uninstall environment: '${INSTALL_DIR}/$(basename "${0}")' --remove"
        echo "To display this help: '${INSTALL_DIR}/$(basename "${0}")' --help"
    fi
}

function remove() {
    echo "[INFO] removing login_afraid_org environment"
    cd "$(dirname "$0")" || die "failed to change to $(dirname "$0")"
    rm -rf activate || echo '[WARN] failed to remove "activate" script'
    rm -rf ../build || echo '[WARN] failed to remove PyInstaller build folder'
    rm -rf ../.venv || echo '[WARN] failed to remove virtual environment'
    rm -rf ../pdm.lock || echo '[WARN] failed to remove PDM lock file'
    rm -rf ../.pdm.* || echo '[WARN] failed to remove PDM config files'
    rm -rf install-pdm.py || echo '[WARN] failed to remove PDM installer'
    rm -rf pdm || echo '[WARN] failed to remove PDM installation'
    [ -z "${_LAO_PATH}" ] || echo "type \"source '$(pwd)/deactivate'\" to finish removing login_afraid_org environment"
    exit
}

for arg in "${@}"; do
    case ${arg,,} in
        -h | --help)
            help
            exit 0
            ;;
        --remove)
            remove
            ;;
    esac
done

echo "[INFO] Installing login_afraid_org environment"
# assert required commands and Python version
[[ -x $(command -v dirname) ]] || die 'command "dirname" is not available'
[[ -x $(command -v curl) ]] || die 'command "curl" is not available'
python="$(command -v python3 2>/dev/null)"
[[ -n ${python} ]] || python="$(command -v python 2>/dev/null)"
[[ -x ${python} ]] || die 'no Python command found'
[[ $(${python} --version) =~ ^[^0-9]*(([0-9]+)"."([0-9]+)".".*)$ ]] || die "failed to get version of \"${python}\""
[[ ${BASH_REMATCH[2]} -ge 3 ]] || die "Python version 3.8 or greater required, found: ${BASH_REMATCH[1]}"
[[ ${BASH_REMATCH[2]} -gt 3 || ${BASH_REMATCH[3]} -gt 8 ]] || die "Python version 3.8 or greater required, found: ${BASH_REMATCH[1]}"

# installation directory
cd "$(dirname "$0")" || die "failed to change to $(dirname "$0")"
INSTALL_DIR="$(pwd)" || die "failed to determine INSTALL_DIR"
export INSTALL_DIR
if [[ -e "${INSTALL_DIR}/activate" ]]; then
    echo "[ERROR] Environment already setup."
    echo
    help
    exit 1
fi

# fetch PDM
curl -sSLO https://pdm-project.org/install-pdm.py || die "failed to download PDM installer"
curl -sSL https://pdm-project.org/install-pdm.py.sha256 | shasum -a 256 -c - 2>/dev/null >/dev/null || die "downloaded PDM installer corrupt: checksum mismatch"

# prepare environment
# shellcheck disable=SC2016
{
    echo '[ -z "${_LAO_PATH}" ] || export PATH="${_LAO_PATH}"'
    echo 'export _LAO_PATH="${PATH}"'
    echo 'export PDM_HOME="'"${INSTALL_DIR}"'/pdm"'
    echo '[ -n "${_LAO_XDG_DATA_HOME}" ] || export _LAO_XDG_DATA_HOME="${XDG_DATA_HOME}"'
    echo 'export XDG_DATA_HOME="${PDM_HOME}/share"'
    echo '[ -n "${_LAO_XDG_CONFIG_HOME}" ] || export _LAO_XDG_CONFIG_HOME="${XDG_CONFIG_HOME}"'
    echo 'if [[ -n "${XDG_CONFIG_HOME}" && ! -e "${PDM_HOME}/config/login_afraid_org" ]]; then'
    echo '    [ -e "${XDG_CONFIG_HOME}/login_afraid_org" ] || mkdir -p "${XDG_CONFIG_HOME}/login_afraid_org"'
    echo '    [ -e "${PDM_HOME}/config" ] || mkdir -p "${PDM_HOME}/config"'
    echo '    ln -s "${XDG_CONFIG_HOME}/login_afraid_org" "${PDM_HOME}/config/login_afraid_org"'
    echo 'elif [ ! -e "${PDM_HOME}/config/login_afraid_org" ]; then'
    echo '    [ -e ~/.config/login_afraid_org ] || mkdir -p ~/.config/login_afraid_org'
    echo '    [ -e "${PDM_HOME}/config" ] || mkdir -p "${PDM_HOME}/config"'
    echo '    ln -s ~/.config/login_afraid_org "${PDM_HOME}/config/login_afraid_org"'
    echo 'fi'
    echo 'export XDG_CONFIG_HOME="${PDM_HOME}/config"'
    echo '[ -n "${_LAO_XDG_CACHE_HOME}" ] || export _LAO_XDG_CACHE_HOME="${XDG_CACHE_HOME}"'
    echo 'export XDG_CACHE_HOME="${PDM_HOME}/cache"'
    echo 'export PDM_CACHE_DIR="${XDG_CACHE_HOME}/pdm"'
    echo '[ -n "${_LAO_XDG_STATE_HOME}" ] || export _LAO_XDG_STATE_HOME="${XDG_STATE_HOME}"'
    echo 'export XDG_STATE_HOME="${PDM_HOME}/state"'
    echo 'export PDM_LOG_DIR="${XDG_STATE_HOME}/log"'
    echo 'export PATH="${PDM_HOME}/bin:'"${INSTALL_DIR}"':${PATH}"'
} >activate || die 'failed to write "activate" script'
source activate || die "failed to source activate script"

# install PDM
while IFS=$'\n' read -r line; do
    echo "[INFO] ${line}"
done < <("${python}" -u install-pdm.py -p "${PDM_HOME}" 2>&1) || die "failed to install PDM"

# setup project
cd "$(dirname "${INSTALL_DIR}")" || die "failed to change to \"$(dirname "${INSTALL_DIR}")\""
RUN_DIR="$(pwd)" || die "failed to determine RUN_DIR"
export RUN_DIR
while IFS=$'\n' read -r line; do
    echo "[INFO] ${line}"
done < <(pdm update --dev --update-all --no-editable --no-self --with dev 2>&1) || die '"pdm init" failed to initialize login_afraid_org'

echo
echo '[INFO] All setup'
echo
help

exit 0
