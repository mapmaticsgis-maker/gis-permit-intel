import os
import re

STOPWORDS = {
    "SHP", "LSE", "STATUS", "UNIT", "UNITS", "ABS", "OSR", "TITLE", "LGL",
    "WORK", "EXPORT", "MOR", "AER", "LTR", "PDF", "MXD", "NEW", "OLD",
    "FINAL", "DRAFT",
}

MIN_TOKEN_LEN = 3
MIN_DIGIT_SIGNATURE_LEN = 4


def normalize(name):
    return re.sub(r"[^A-Za-z0-9]", "", name).upper()


def alnum_tokens(name):
    tokens = set()
    for t in re.findall(r"[A-Za-z0-9]+", name):
        upper = t.upper()
        if len(upper) >= MIN_TOKEN_LEN and upper not in STOPWORDS:
            tokens.add(upper)
    return tokens


def digit_signature(name):
    return "".join(re.findall(r"\d", name))


def match_candidate(mxd_basename, candidate_name):
    candidate_stem = os.path.splitext(candidate_name)[0]

    norm_mxd = normalize(mxd_basename)
    norm_candidate = normalize(candidate_stem)
    if norm_mxd and norm_mxd in norm_candidate:
        return {"confidence": "Exact", "matched_tokens": [mxd_basename]}

    mxd_tokens = alnum_tokens(mxd_basename)
    candidate_tokens = alnum_tokens(candidate_name)
    shared = sorted(mxd_tokens & candidate_tokens)

    mxd_digits = digit_signature(mxd_basename)
    digit_match = (
        len(mxd_digits) >= MIN_DIGIT_SIGNATURE_LEN
        and mxd_digits in digit_signature(candidate_name)
    )

    if not shared and not digit_match:
        return None

    matched_tokens = list(shared)
    if digit_match:
        matched_tokens.append("digits:" + mxd_digits)

    return {"confidence": "Token", "matched_tokens": matched_tokens}
