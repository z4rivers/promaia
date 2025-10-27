"""
Utility functions for parsing command-line query arguments.
"""


def parse_vs_queries_with_params(argv):
    """
    Parse -vs queries with their per-query -tk/-th parameters from an argv list.

    Args:
        argv: List of command-line arguments (e.g., sys.argv or shlex.split result)

    Returns:
        List of dicts with structure: {'query': str, 'top_k': int, 'threshold': float}
    """
    vs_queries_structured = []

    # Find all -vs positions and pair them with following -tk/-th
    vs_indices = [i for i, arg in enumerate(argv) if arg in ['-vs', '--vector-search']]

    for idx_pos, vs_idx in enumerate(vs_indices):
        # Get the query text (everything after -vs until next flag)
        query_parts = []
        i = vs_idx + 1
        while i < len(argv) and not argv[i].startswith('-'):
            query_parts.append(argv[i])
            i += 1
        query_text = ' '.join(query_parts)

        # Find -tk and -th for this query (between this -vs and next -vs)
        next_vs_idx = vs_indices[idx_pos + 1] if idx_pos + 1 < len(vs_indices) else len(argv)
        top_k = 20  # default
        threshold = 0.75  # default

        # Look for -tk/-th in the range after this query's text
        for j in range(i, next_vs_idx):
            if argv[j] in ['-tk', '--top-k'] and j + 1 < len(argv):
                try:
                    top_k = int(argv[j + 1])
                except ValueError:
                    pass
            elif argv[j] in ['-th', '--threshold'] and j + 1 < len(argv):
                try:
                    threshold = float(argv[j + 1])
                except ValueError:
                    pass

        vs_queries_structured.append({
            'query': query_text,
            'top_k': top_k,
            'threshold': threshold
        })

    return vs_queries_structured
