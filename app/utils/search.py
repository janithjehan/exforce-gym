from sqlalchemy import or_, cast, String


def parse_search_terms(raw):
    """Split a comma-separated search string into stripped, non-empty terms."""
    if not raw:
        return []
    return [t.strip() for t in raw.split(',') if t.strip()]


def multi_term_filter(terms, columns):
    """OR filter across terms: a row matches if ANY term matches ANY of the given columns."""
    # Postgres' ILIKE only accepts text operands, so non-string columns
    # (Integer, Numeric, ...) must be cast before comparing.
    castable = [
        column if column.type.python_type is str else cast(column, String)
        for column in columns
    ]
    return or_(*(
        or_(*(column.ilike(f'%{term}%') for column in castable))
        for term in terms
    ))

# def multi_term_filter(terms, columns):
#     """OR filter across terms: a row matches if ANY term matches ANY of the given columns."""
#     return or_(*(
#         or_(*(column.ilike(f'%{term}%') for column in columns))
#         for term in terms
#     ))