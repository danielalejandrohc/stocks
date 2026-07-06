import datetime
import re
import unicodedata


def purified_text(text, length_limit=1000, debug=False):
    """
    Clean and extract article body from news content.
    Removes headers, ticker lists, footers, ads, and HTML artifacts.
    Returns cleaned text limited to specified character count.
    """
    if not text:
        return ""

    # 1. Normalize text & remove HTML artifacts
    text = unicodedata.normalize('NFKD', text)
    text = text.replace("&nbsp;", " ")

    # 2. Remove header and ticker list
    header_patterns = [
        r"(?:In This Article:|This Article:)",
        r"(?:In this article:|This article:)",
    ]

    for pattern in header_patterns:
        parts = re.split(pattern, text, maxsplit=1, flags=re.IGNORECASE)
        if len(parts) > 1:
            lines = parts[1].split('\n')
            for i, line in enumerate(lines):
                line_strip = line.strip()
                if not line_strip:
                    continue
                if re.fullmatch(r"[\^A-Z0-9\.]+", line_strip) and len(line_strip) <= 12:
                    continue
                text = "\n".join(lines[i:])
                break
            break

    # 3. Remove byline + date + read-time header block
    #    e.g. "Josh Schafer · Reporter\nSat, Jun 28, 2025, 4:00 AM 2 min read"
    text = re.sub(
        r"^[^\n]{3,50}\n"                                  # author line
        r"(?:[A-Za-z]{3},\s+)?[A-Za-z]{3}\s+\d{1,2},\s+\d{4}"  # date
        r"(?:,?\s+\d{1,2}:\d{2}\s+(?:AM|PM))?"             # optional time
        r"(?:\s+\d+\s+min\s+read)?",                        # optional read time
        "", text, count=1
    )

    # 4. Remove footer patterns
    footer_patterns = [
        r"(?:PREMIUM\s+)?Upgrade to read.*",
        r"Story Continues.*",
        r"Terms and Privacy Policy.*",
        r"Privacy Dashboard.*",
        r"Your Privacy Choices.*",
        r"CA Privacy Notice.*",
        r"Already have a subscription\?.*",
        r"View original content.*",
        r"Related articles.*",
        r"(?:READ NEXT|NEXT STEPS|Next Steps).*",
        r"Disclosure:.*",
        r"Contact the press release distributor.*",
    ]
    combined_pattern = "|".join(f"(?:{p})" for p in footer_patterns)
    text = re.split(combined_pattern, text, flags=re.IGNORECASE | re.DOTALL)[0]

    # 5. Remove mid-article promotional / ad blocks (line-by-line)
    promo_patterns = re.compile(
        r"(?:"
        r"Sign up for .*|Subscribe\b.*|By subscribing.*"
        r"|Elevate Your Investing Strategy.*"
        r"|Take advantage of .*(?:Premium|discount|off).*"
        r"|Make smarter investment decisions.*"
        r"|Don'?t Miss:?.*"
        r"|Trending:.*"
        r"|See also:.*"
        r"|While we acknowledge the potential of .*"
        r"|If you'?re looking for an? .*(?:undervalued|stock).*see our.*"
        r"|Invest early in .*"
        r"|(?:Peter Thiel|Warren Buffett) turned \$.*"
        r")$",
        re.IGNORECASE | re.MULTILINE,
    )
    text = promo_patterns.sub("", text)

    # 6. Remove image alt-text lines (short descriptive sentences between paragraphs)
    #    e.g. "An assembly line in a semiconductor factory, with workers at their stations."
    text = re.sub(
        r"\n(?:A |An |The )[A-Za-z ,'()-]{20,120}\.\n",
        "\n", text
    )

    # 7. Remove duplicate headline (first body line repeated later)
    lines = text.strip().split("\n")
    if len(lines) > 2:
        headline = lines[0].strip()
        if headline and len(headline) > 20:
            cleaned = [lines[0]]
            for line in lines[1:]:
                if line.strip() != headline:
                    cleaned.append(line)
            lines = cleaned
        text = "\n".join(lines)

    # 8. Clean up formatting
    text = re.sub(r"^[ \t\n\r\f\v]+", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = text.strip()

    # 9. Smart truncation at sentence boundary
    if len(text) > length_limit:
        truncated = text[:length_limit]
        last_period = truncated.rfind('.')
        if last_period > length_limit * 0.8:
            text = truncated[:last_period + 1].strip()
        else:
            text = truncated.strip()
    return text


def select_local_model():
    """
    Lists compatible summarization models for RTX 4060 8GB VRAM and lets the user choose.
    Returns the Hugging Face model ID and whether quantization is needed.
    """
    models = [
        # --- Best Quality (Recommended for stock summarization) ---
        ("deepseek-r1:8b", "deepseek-r1:8b"),
        ("gemma:7b", "gemma:7b"),
        ("gemma4:e4b", "gemma4:e4b"),
        ("gemma4:e2b", "gemma4:e2b"),
    ]

    print("\n=== Select a summarization model to load ===")
    for i, (name, _) in enumerate(models, start=1):
        print(f"{i}. {name}")
    choice = input("Enter number: ").strip()

    try:
        idx = int(choice) - 1
        if idx < 0 or idx >= len(models):
            raise ValueError
    except ValueError:
        print("Invalid choice, defaulting to Mistral 7B Instruct v0.3.")
        idx = 0

    name, hf_id = models[idx]
    print(f"\nYou selected: {name}\n")
    return name, hf_id


def extract_first_date(text: str):
    """
    Extract the first date found in the input text and return it as a datetime.datetime.
    Supported examples include:
    - "Sat, Jun 28, 2025, 10:00 AM"
    - "Sat, Jun 28, 2025"
    - "Jun 28, 2025, 10:00 AM"
    - "Jun 28, 2025"

    Returns None if no date is found or parsable.
    """
    if not text:
        return None

    # Candidate regex patterns (month/day names in English)
    patterns = [
        r"\b(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun),\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},\s+\d{4},\s+\d{1,2}:\d{2}\s+(?:AM|PM)\b",
        r"\b(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun),\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},\s+\d{4}\b",
        r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},\s+\d{4},\s+\d{1,2}:\d{2}\s+(?:AM|PM)\b",
        r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},\s+\d{4}\b",
    ]

    def _normalize_tokens(s: str) -> str:
        # Title-case weekday/month names; uppercase AM/PM
        def repl(m):
            w = m.group(0)
            if w.lower() in ("am", "pm"):
                return w.upper()
            return w.title()
        s = re.sub(r"[A-Za-z]+", repl, s)
        # Collapse multiple spaces
        s = re.sub(r"\s+", " ", s).strip()
        return s

    # Try to find and parse with a set of common formats
    parse_formats = [
        "%a, %b %d, %Y, %I:%M %p",
        "%a, %b %d, %Y %I:%M %p",
        "%a, %b %d, %Y",
        "%b %d, %Y, %I:%M %p",
        "%b %d, %Y %I:%M %p",
        "%b %d, %Y",
    ]

    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if not m:
            continue
        candidate = _normalize_tokens(m.group(0))
        for fmt in parse_formats:
            try:
                date = datetime.datetime.strptime(candidate, fmt)
                return date
            except ValueError:
                continue
    return None
