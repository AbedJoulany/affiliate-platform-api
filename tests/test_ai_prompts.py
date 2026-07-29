from decimal import Decimal

from app.ai.product_context import ProductContext
from app.ai.prompts import build_marketing_prompt
from app.core.enums import ContentLanguage, ContentLength, ContentType, ToneProfile


def test_build_marketing_prompt_includes_profile_and_modifiers():
    context = ProductContext(
        product_id=None,
        title="Wireless Earbuds",
        product_url="https://example.com/p",
        description="Compact earbuds",
        price=Decimal("29.99"),
        discount=Decimal("20"),
        rating=Decimal("4.5"),
        sales=1200,
        reviews=340,
        image_url=None,
    )

    prompt = build_marketing_prompt(
        context,
        content_type=ContentType.FACEBOOK,
        tone=ToneProfile.URGENT,
        language=ContentLanguage.AR,
        length=ContentLength.SHORT,
        instruction_modifiers=["strengthen_cta", "add_emojis"],
    )

    assert "facebook" in prompt
    assert "عاجلة" in prompt
    assert "قصير" in prompt
    assert "تقوّ عبارة الحث" in prompt or "قوّ عبارة الحث" in prompt
    assert "رموزًا تعبيرية" in prompt
    assert "Wireless Earbuds" in prompt
