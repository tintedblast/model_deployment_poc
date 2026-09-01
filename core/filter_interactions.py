def filter_interactions(interactions: list[dict], summary_type: str) -> list[dict]:
    if summary_type == "complaint":
        return interactions
    return [i for i in interactions if i["channel"] == summary_type]
