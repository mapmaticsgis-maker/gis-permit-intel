import os
import re

STOPWORDS = {
    "SHP", "LSE", "STATUS", "UNIT", "UNITS", "ABS", "OSR", "TITLE", "LGL",
    "WORK", "EXPORT", "MOR", "AER", "LTR", "PDF", "MXD", "NEW", "OLD",
    "FINAL", "DRAFT",
    # print/paper sizes -- appear across unrelated projects, not identifying
    "11X17", "24X36", "36X24", "85X14", "6X45", "48X42", "77X38", "42X42",
    "7X7", "26X34",
}

MIN_TOKEN_LEN = 4
MIN_DIGIT_SIGNATURE_LEN = 4
YEAR_RANGE = range(1900, 2100)


def normalize(name):
    return re.sub(r"[^A-Za-z0-9]", "", name).upper()


def _is_year_like(run):
    return len(run) == 4 and run.isdigit() and int(run) in YEAR_RANGE


def alnum_tokens(name):
    tokens = set()
    for t in re.findall(r"[A-Za-z0-9]+", name):
        upper = t.upper()
        if len(upper) >= MIN_TOKEN_LEN and upper not in STOPWORDS and not _is_year_like(upper):
            tokens.add(upper)
    return tokens


def digit_signature(name):
    runs = re.findall(r"\d+", name)
    return "".join(r for r in runs if not _is_year_like(r))


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
