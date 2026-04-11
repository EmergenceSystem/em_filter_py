from em_filter.html import (
    strip_scripts, get_text, extract_elements,
    extract_attribute, decode_html_entities, should_skip_link,
)

def test_strip_scripts():
    html = '<p>Hello</p><script>alert(1)</script><p>World</p>'
    assert 'script' not in strip_scripts(html)
    assert 'Hello' in strip_scripts(html)

def test_strip_scripts_multiline():
    html = '<p>A</p><script type="text/javascript">\nvar x=1;\n</script><p>B</p>'
    result = strip_scripts(html)
    assert 'var x' not in result
    assert 'A' in result and 'B' in result

def test_get_text():
    assert get_text('<p>Hello <b>world</b></p>') == 'Hello world'

def test_get_text_no_tags():
    assert get_text('plain text') == 'plain text'

def test_extract_elements_tag():
    html = '<div>A</div><div>B</div>'
    elems = extract_elements(html, 'div')
    assert 'A' in elems
    assert 'B' in elems

def test_extract_elements_class():
    html = '<li class="b_algo">item</li><li>other</li>'
    elems = extract_elements(html, 'li.b_algo')
    assert len(elems) == 1
    assert 'item' in elems[0]

def test_extract_elements_dot_class():
    html = '<p class="foo">yes</p><p>no</p>'
    elems = extract_elements(html, '.foo')
    assert any('yes' in e for e in elems)

def test_extract_attribute():
    assert extract_attribute('<a href="/page">link</a>', 'href') == '/page'

def test_extract_attribute_missing():
    assert extract_attribute('<a>link</a>', 'href') is None

def test_decode_html_entities_numeric():
    assert decode_html_entities('&#233;') == 'é'

def test_decode_html_entities_hex():
    assert decode_html_entities('&#xE9;') == 'é'

def test_decode_html_entities_named():
    assert decode_html_entities('&eacute;') == 'é'
    assert decode_html_entities('&amp;') == '&'
    assert decode_html_entities('&lt;') == '<'
    assert decode_html_entities('&gt;') == '>'
    assert decode_html_entities('&quot;') == '"'

def test_decode_html_entities_combined():
    result = decode_html_entities('caf&eacute; &amp; croissant')
    assert result == 'café & croissant'

def test_should_skip_link_not_http():
    assert should_skip_link('ftp://example.com', []) is True

def test_should_skip_link_excluded():
    assert should_skip_link('https://ads.example.com/x', ['ads.example.com']) is True

def test_should_skip_link_ok():
    assert should_skip_link('https://example.com', ['ads.com']) is False
