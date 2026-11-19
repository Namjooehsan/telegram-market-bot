from pathlib import Path


def test_miniapp_has_clean_category_dashboard_and_featured_ticker():
    html = (Path(__file__).resolve().parents[1] / "miniapps" / "index.html").read_text(encoding="utf-8")
    assert 'id="homeView"' in html
    assert 'id="branchGrid"' in html
    assert 'id="catalogView"' in html
    assert 'id="backHome"' in html
    assert 'id="tickerTrack"' in html
    assert "@keyframes nova-marquee" in html
    assert "function showCategory(category)" in html
    assert "function showHome()" in html


def test_miniapp_dashboard_keeps_products_out_of_home_page():
    html = (Path(__file__).resolve().parents[1] / "miniapps" / "index.html").read_text(encoding="utf-8")
    home_start = html.index('<div class="home-view" id="homeView">')
    catalog_start = html.index('<div class="catalog-view" id="catalogView"')
    assert home_start < catalog_start
    assert 'id="paidGrid"' in html[catalog_start:]
