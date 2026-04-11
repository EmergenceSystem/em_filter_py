"""
echo_filter — exemple minimal d'un agent em_filter Python.

Connecte à em_disco en tant que 'echo_filter', annonce les capabilities
["search", "query", "echo"] et retourne chaque query sous forme d'embryo URL.

Usage:
    python examples/echo_filter.py

Avec un broker personnalisé:
    EM_DISCO_HOST=disco.example.com EM_DISCO_PORT=443 \
    EM_FILTER_JWT_TOKEN=eyJ... python examples/echo_filter.py

Test depuis le shell Erlang (em_disco running):
    em_disco:query(<<"hello world">>).
    %% → [#{<<"type">> => <<"url">>, <<"properties">> => #{...}}]
"""
import logging
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from em_filter import AgentConfig, FilterRunner

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)


def handle(body: str, memory: dict) -> tuple:
    """Echo the query body as a URL embryo. Memory unused (stateless)."""
    logging.getLogger("echo_filter").info("query: %s", body)
    result = [
        {
            "type": "url",
            "properties": {
                "url": "https://example.com",
                "title": f"Echo: {body}",
            },
        }
    ]
    return result, memory


if __name__ == "__main__":
    FilterRunner("echo_filter", handle, AgentConfig()).run()
