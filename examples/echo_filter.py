"""
echo_filter — minimal em_filter agent example.

Returns one URL embryo echoing the query body. Runs in either transport
mode via EM_FILTER_MODE (relay is the default, no inbound port needed):

    python examples/echo_filter.py                        # relay (default)
    EM_FILTER_MODE=direct EM_FILTER_QUERY_PORT=9600 \
        python examples/echo_filter.py                     # direct HTTP + gossip

Point at a non-default disco with EM_DISCO_HOST / EM_DISCO_PORT.
"""
import logging
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from em_filter import FilterRunner

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def handle(body: str, memory: dict) -> tuple:
    results = [{"url": "https://example.com", "title": f"Echo: {body}", "resume": body}]
    return results, memory


if __name__ == "__main__":
    FilterRunner("echo_filter", handle, capabilities=["search", "query", "echo"]).run()
