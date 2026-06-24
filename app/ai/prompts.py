from decimal import Decimal

from app.ai.product_context import ProductContext


def build_arabic_marketing_prompt(context: ProductContext) -> str:
    lines = [
        "اكتب محتوى تسويقي باللغة العربية لمنتج affiliate marketing لنشره على Telegram.",
        "",
        "معلومات المنتج:",
        f"- العنوان: {context.title}",
        f"- رابط المنتج: {context.product_url}",
    ]

    if context.description:
        lines.append(f"- الوصف: {context.description}")

    if context.price is not None:
        discounted_price = context.price
        discount = context.discount or Decimal("0.00")
        if discount > 0:
            discount_amount = context.price * discount / 100
            discounted_price = context.price - discount_amount
        lines.extend(
            [
                f"- السعر الأصلي: {context.price}",
                f"- نسبة الخصم: {discount}%",
                f"- السعر بعد الخصم: {discounted_price:.2f}",
            ]
        )

    if context.rating is not None:
        lines.append(f"- التقييم: {context.rating}/5")

    if context.sales is not None:
        lines.append(f"- عدد المبيعات: {context.sales}")

    if context.reviews is not None:
        lines.append(f"- عدد المراجعات: {context.reviews}")

    if context.image_url:
        lines.append(f"- صورة المنتج: {context.image_url}")

    if context.price is None and context.rating is None:
        lines.append(
            "- ملاحظة: بعض تفاصيل المنتج غير متوفرة، استخدم العنوان والوصف والرابط لكتابة محتوى مقنع."
        )

    lines.extend(
        [
            "",
            "المطلوب:",
            "1. اكتب باللغة العربية الفصحى المعاصرة (واضحة وجذابة).",
            "2. استخدم emojis بشكل معتدل.",
            "3. أبرز فوائد المنتج وسبب الشراء الآن.",
            "4. أضف call-to-action واضح مع الرابط.",
            "5. اجعل النص مناسباً لمنشور Telegram (150-250 كلمة تقريباً).",
            "6. لا تذكر أن النص مكتوب بواسطة AI.",
        ]
    )

    return "\n".join(lines)
