from decimal import Decimal

from app.ai.product_context import ProductContext
from app.core.enums import ContentLanguage, ContentLength, ContentType, ToneProfile

CONTENT_TYPE_GUIDANCE: dict[ContentType, str] = {
    ContentType.SOCIAL: (
        "اكتب منشورًا مناسبًا للشبكات الاجتماعية (قصير، جذاب، قابل للمشاركة)."
    ),
    ContentType.DESCRIPTION: (
        "اكتب وصف منتج واضحًا يبرز المواصفات والفوائد ونقاط البيع."
    ),
    ContentType.TELEGRAM: (
        "اكتب منشورًا مناسبًا لتلغرام مع فقرات قصيرة وحث واضح على الشراء."
    ),
    ContentType.FACEBOOK: (
        "اكتب إعلان فيسبوك يركّز على الاهتمام والرغبة والحث على النقر."
    ),
    ContentType.BLOG: (
        "اكتب مقالًا قصيرًا بعناوين فرعية وفقرات واضحة وخاتمة تحث على الشراء."
    ),
    ContentType.EMAIL: (
        "اكتب رسالة بريد إلكتروني تسويقية مع موضوع مقترح ونص الرسالة وCTA."
    ),
}

TONE_GUIDANCE: dict[ToneProfile, str] = {
    ToneProfile.PROFESSIONAL: "النبرة: مهنية وموثوقة.",
    ToneProfile.FRIENDLY: "النبرة: ودّية وقريبة من القارئ.",
    ToneProfile.LUXURY: "النبرة: فاخرة وأنيقة.",
    ToneProfile.TECHNICAL: "النبرة: تقنية ودقيقة مع تفاصيل مفيدة.",
    ToneProfile.URGENT: "النبرة: عاجلة تحفّز اتخاذ القرار الآن.",
    ToneProfile.MINIMAL: "النبرة: بسيطة ومباشرة بلا حشو.",
    ToneProfile.PERSUASIVE: "النبرة: إقناعية تركّز على الفوائد والدليل.",
    ToneProfile.FUNNY: "النبرة: خفيفة وفكاهية باعتدال دون ابتذال.",
}

LANGUAGE_GUIDANCE: dict[ContentLanguage, str] = {
    ContentLanguage.AR: "اكتب باللغة العربية الفصحى المعاصرة (واضحة وجذابة).",
    ContentLanguage.EN: "Write in clear, modern English.",
    ContentLanguage.FR: "Rédige en français clair et moderne.",
    ContentLanguage.DE: "Schreibe in klarem, modernem Deutsch.",
}

LENGTH_GUIDANCE: dict[ContentLength, str] = {
    ContentLength.SHORT: "الطول المستهدف: قصير (حوالي 60–120 كلمة).",
    ContentLength.MEDIUM: "الطول المستهدف: متوسط (حوالي 150–250 كلمة).",
    ContentLength.LONG: "الطول المستهدف: طويل (حوالي 300–500 كلمة).",
}

MODIFIER_GUIDANCE: dict[str, str] = {
    "add_emojis": "أضف رموزًا تعبيرية معتدلة وذات صلة.",
    "strengthen_cta": "قوّ عبارة الحث على الشراء واجعل الرابط بارزًا.",
    "shorten": "اختصر النص مع الحفاظ على الفائدة الأساسية.",
    "increase_urgency": "زد طابع العجلة دون مبالغة أو تضليل.",
    "improve_seo": "حسّن العناوين والكلمات المفتاحية لسهولة القراءة والبحث.",
}


def build_marketing_prompt(
    context: ProductContext,
    *,
    content_type: ContentType = ContentType.TELEGRAM,
    tone: ToneProfile = ToneProfile.PERSUASIVE,
    language: ContentLanguage = ContentLanguage.AR,
    length: ContentLength = ContentLength.MEDIUM,
    instruction_modifiers: list[str] | None = None,
) -> str:
    """Build a profile-aware marketing prompt for the active content session."""
    modifiers = instruction_modifiers or []
    lines = [
        "أنشئ محتوى تسويقيًا لمنتج affiliate marketing وفق الإعدادات التالية.",
        "",
        f"المنصة / نوع المحتوى: {content_type.value}",
        CONTENT_TYPE_GUIDANCE[content_type],
        TONE_GUIDANCE[tone],
        LANGUAGE_GUIDANCE[language],
        LENGTH_GUIDANCE[length],
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
            "- ملاحظة: بعض تفاصيل المنتج غير متوفرة، استخدم العنوان والوصف والرابط "
            "لكتابة محتوى مقنع."
        )

    lines.extend(
        [
            "",
            "المطلوب:",
            "1. التزم باللغة والنبرة والطول المحددين أعلاه.",
            "2. أبرز فوائد المنتج وسبب الشراء الآن.",
            "3. أضف call-to-action واضحًا مع الرابط.",
            "4. نظّم النص بعناوين أو نقاط عند الحاجة لتسهيل القراءة.",
            "5. لا تذكر أن النص مكتوب بواسطة AI.",
        ]
    )

    active_modifiers = [MODIFIER_GUIDANCE[key] for key in modifiers if key in MODIFIER_GUIDANCE]
    if active_modifiers:
        lines.append("")
        lines.append("تعديلات إضافية مطلوبة:")
        for index, guidance in enumerate(active_modifiers, start=1):
            lines.append(f"{index}. {guidance}")

    return "\n".join(lines)


def build_arabic_marketing_prompt(context: ProductContext) -> str:
    """Backward-compatible wrapper for Telegram Arabic medium content."""
    return build_marketing_prompt(
        context,
        content_type=ContentType.TELEGRAM,
        tone=ToneProfile.PERSUASIVE,
        language=ContentLanguage.AR,
        length=ContentLength.MEDIUM,
    )
