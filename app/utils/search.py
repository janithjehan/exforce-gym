from sqlalchemy import or_


def parse_search_terms(raw):
    """Split a comma-separated search string into stripped, non-empty terms."""
    if not raw:
        return []
    return [t.strip() for t in raw.split(',') if t.strip()]


def multi_term_filter(terms, columns):
    """OR filter across terms: a row matches if ANY term matches ANY of the given columns."""
    return or_(*(
        or_(*(column.ilike(f'%{term}%') for column in columns))
        for term in terms
    ))