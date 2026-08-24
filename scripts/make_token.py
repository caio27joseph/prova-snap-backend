#!/usr/bin/env -S uv run python
"""Dev/evaluator tooling: mint a mock Keycloak JWT for manual API calls.

With a real Keycloak this script would not exist — tokens would come from the
realm. It reuses the test token factory (tests/token_helpers.py) so manual
tokens and test tokens are always structurally identical.

Usage: scripts/make_token.py joao [--azp analytics-api] [--expires-in 3600]
"""

import argparse
import sys
from pathlib import Path

# Run as a plain script from anywhere: put the repo root on sys.path so the
# `app` and `tests` packages resolve without installing the project.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.auth import mock_users  # noqa: E402
from tests.token_helpers import make_token  # noqa: E402

PERSONAS = {
    "joao": mock_users.JOAO,
    "maria": mock_users.MARIA,
    "pedro": mock_users.PEDRO,
    "ana": mock_users.ANA,
    "carlos": mock_users.CARLOS,
    "outro": mock_users.OUTRO,
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("persona", choices=sorted(PERSONAS))
    parser.add_argument("--azp", default="analytics-api", help="issuing client (token azp)")
    parser.add_argument("--expires-in", type=int, default=3600, help="lifetime in seconds")
    args = parser.parse_args()

    print(make_token(PERSONAS[args.persona], azp=args.azp, expires_in=args.expires_in))


if __name__ == "__main__":
    main()
