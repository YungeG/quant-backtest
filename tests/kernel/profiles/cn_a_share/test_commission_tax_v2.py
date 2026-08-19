from __future__ import annotations

from crypto_quant_trading.profiles.cn_a_share import (
    CnAShareExecutionAccessRoute,
    CnAShareFeeProductClass,
    project_cn_a_share_domestic_ordinary_fee_rules_v2,
)
from tests.kernel.profiles.cn_a_share._commission_tax_fixtures import (
    market_rule_book,
    tax_rule_book,
)


def test_projection_rejects_v1_xshg_source_before_output() -> None:
    result = project_cn_a_share_domestic_ordinary_fee_rules_v2(
        market_rule_book(), tax_rule_book()
    )
    assert result.code.value == "non_xshe_market_source"


def test_projection_maps_xshe_v1_bands_with_explicit_hkscc_ref() -> None:
    source_market = market_rule_book()
    source_tax = tax_rule_book()
    market = type(source_market)(
        source_market.rule_book_key,
        source_market.rule_book_version,
        tuple(band for band in source_market.bands if band.venue_id.value == "xshe"),
    )
    tax = type(source_tax)(
        source_tax.rule_book_key,
        source_tax.rule_book_version,
        tuple(band for band in source_tax.bands if band.venue_id.value == "xshe"),
    )
    result = project_cn_a_share_domestic_ordinary_fee_rules_v2(market, tax)
    assert result.access_route is CnAShareExecutionAccessRoute.DOMESTIC
    assert result.fee_product_class is CnAShareFeeProductClass.ORDINARY_A_SHARE
    assert all(not band.hkscc_transfer_applies for band in result.market_fee_rule_book.bands)
    assert all(band.hkscc_transfer_source_refs for band in result.market_fee_rule_book.bands)
