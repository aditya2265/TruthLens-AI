"""Synthetic test fixtures for automated testing ONLY.

NON-NEGOTIABLE RULE: These synthetic fixtures are exclusively for isolated
unit tests. They must NEVER be used to train production models or presented
as genuine dataset evaluation.
"""
import pandas as pd


def get_synthetic_raw_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Returns small synthetic DataFrames mimicking Fake.csv and True.csv.

    These are strictly for pipeline, preprocessing, and unit tests.
    """
    fake_data = {
        "title": [
            "SHOCKING: Secret alien plot uncovered in Washington!",
            "BREAKING: Miracle cure discovered by rogue scientist!",
            "You won't believe what this politician did next!!!",
            "UNBELIEVABLE: Hidden documents reveal unbelievable conspiracy!",
            "SHOCKING: Secret alien plot uncovered in Washington!",  # duplicate
        ],
        "text": [
            "According to unverified blog sources, secret aliens have taken over several government departments in Washington. The mainstream media refuses to report this unbelievable reality!",
            "A rogue scientist claims that drinking lemon water with baking soda immediately destroys all known viruses within 24 hours. Medical experts are allegedly terrified of this secret cure!",
            "Watch this shocking video where a high-ranking official walks out of a hearing after being confronted with explosive allegations by reporters!",
            "Classified files leaked to an anonymous website suggest a secret plot orchestrated by global elites to control global weather patterns and agriculture.",
            "According to unverified blog sources, secret aliens have taken over several government departments in Washington. The mainstream media refuses to report this unbelievable reality!",  # duplicate
        ],
        "subject": ["News", "Government", "Politics", "News", "News"],
        "date": ["January 1, 2020", "January 2, 2020", "January 3, 2020", "January 4, 2020", "January 1, 2020"],
    }

    true_data = {
        "title": [
            "Senate committee passes bipartisan infrastructure reform bill",
            "Federal Reserve holds interest rates steady following quarterly review",
            "WHO publishes comprehensive guidelines on seasonal influenza vaccination",
            "Treasury Department issues updated guidance on domestic clean energy tax credits",
        ],
        "text": [
            "WASHINGTON (Reuters) - The Senate Finance Committee on Tuesday approved bipartisan infrastructure legislation aimed at modernizing regional water systems and public transit networks across fifteen states.",
            "WASHINGTON (Reuters) - The Federal Reserve announced Wednesday that it will maintain benchmark interest rates at their current target range, citing consistent employment growth and moderate inflation.",
            "GENEVA (Reuters) - The World Health Organization issued new recommendations regarding annual influenza vaccines, highlighting prioritized access for elderly populations and frontline healthcare staff.",
            "WASHINGTON (Reuters) - The United States Treasury Department announced refreshed implementation guidelines regarding clean energy manufacturing tax deductions under recent federal statutes.",
        ],
        "subject": ["politicsNews", "politicsNews", "worldnews", "politicsNews"],
        "date": ["December 15, 2017", "December 16, 2017", "December 17, 2017", "December 18, 2017"],
    }

    return pd.DataFrame(fake_data), pd.DataFrame(true_data)
