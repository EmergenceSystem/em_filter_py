from __future__ import annotations
import re
from typing import Optional

_NAMED_ENTITIES: dict[str, str] = {
    "nbsp": "\u00a0", "amp": "&", "lt": "<", "gt": ">",
    "quot": '"', "apos": "'",
    "eacute": "é", "egrave": "è", "agrave": "à", "ccedil": "ç",
    "ocirc": "ô", "ecirc": "ê", "icirc": "î", "ugrave": "ù",
    "aacute": "á",
}


def strip_scripts(html: str) -> str:
    """Remove all <script>…</script> blocks."""
    return re.sub(r'<script[^>]*>.*?</script>', '', html,
                  flags=re.DOTALL | re.IGNORECASE)


def get_text(html: str) -> str:
    """Strip all HTML tags, returning plain text."""
    return re.sub(r'<[^>]+>', '', html)


def extract_elements(html: str, selector: str) -> list[str]:
    """Extract inner HTML of elements matching a simple CSS selector."""
    pat = _selector_to_pattern(selector)
    return re.findall(pat, html, flags=re.DOTALL | re.IGNORECASE)


def extract_attribute(element: str, attr: str) -> Optional[str]:
    """Extract the value of an attribute from an HTML element string."""
    m = re.search(re.escape(attr) + r'''=['"](.*?)['"]''', element,
                  re.IGNORECASE)
    return m.group(1) if m else None


def decode_html_entities(text: str) -> str:
    """Decode &#N;, &#xHH;, and &name; HTML entities."""
    text = re.sub(r'&#([0-9]+);',
                  lambda m: chr(int(m.group(1))), text)
    text = re.sub(r'&#x([0-9A-Fa-f]+);',
                  lambda m: chr(int(m.group(1), 16)), text)
    text = re.sub(r'&([a-zA-Z]+);',
                  lambda m: _NAMED_ENTITIES.get(m.group(1), m.group(0)), text)
    return text


def should_skip_link(url: str, excluded: list[str]) -> bool:
    """Return True if the URL should be skipped."""
    if not url.startswith("http"):
        return True
    return any(excl in url for excl in excluded)


def _selector_to_pattern(selector: str) -> str:
    if selector == "li.b_algo":
        return r'<li[^>]*class=[\'"]b_algo[\'"][^>]*>(.*?)</li>'
    if selector == "div a":
        return r'<a[^>]*>(.*?)</a>'
    if selector == "div p":
        return r'<p[^>]*>(.*?)</p>'
    if selector.startswith("."):
        cls = re.escape(selector[1:])
        return r'<[^>]*class=[\'"][^\'\"]*' + cls + r'[^\'\"]*[\'"][^>]*>(.*?)</[^>]+>'
    if selector.startswith("#"):
        id_ = re.escape(selector[1:])
        return r'<[^>]*id=[\'"]' + id_ + r'[\'"][^>]*>(.*?)</[^>]+>'
    if selector.startswith("[") and "=" in selector:
        inner = selector[1:].rstrip("]")
        attr, _, val = inner.partition("=")
        val = val.strip("'\"")
        return (r'<[^>]*' + re.escape(attr) + r'=[\'"]' +
                re.escape(val) + r'[\'"][^>]*>(.*?)</[^>]+>')
    if "." in selector:
        tag, cls = selector.split(".", 1)
        return (r'<' + re.escape(tag) + r'[^>]*class=[\'"][^\'\"]*' +
                re.escape(cls) + r'[^\'\"]*[\'"][^>]*>(.*?)</' +
                re.escape(tag) + r'>')
    tag = re.escape(selector)
    return r'<' + tag + r'[^>]*>(.*?)</' + tag + r'>'
