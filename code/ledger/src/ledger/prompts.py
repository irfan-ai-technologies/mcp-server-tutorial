"""Prompts: templates the *user* invokes, not the model.

The primitive everyone skips, because "I can just type that" is true right up
until five people type it five different ways. A prompt is where a domain's
standard question lives, with the vocabulary already correct.

Note what these do not do: they do not call tools, and they do not answer
anything. They assemble a well-formed question and leave the work to the model.
"""

from __future__ import annotations

from ledger.app import mcp


# region: clearance_check
@mcp.prompt(
    name="clearance_check",
    description="Can we license this title, in this territory, on these rights?",
)
def clearance_check(title: str, territory: str, rights: str = "svod") -> str:
    """The question a rights manager asks twenty times a day.

    Worth having as a prompt because the *method* is the valuable part, not the
    wording: check for a conflicting exclusive before checking for an available
    window, or you will confidently clear something that is already sold.
    """
    return (
        f"Can we grant {rights} rights for “{title}” in {territory}?\n\n"
        "Work in this order and show your reasoning:\n"
        "1. Find the title with search_titles. If several match, list them and "
        "stop — do not guess which one is meant.\n"
        "2. Look for an existing exclusive licence covering "
        f"{territory} and {rights}. An exclusive that has not expired blocks "
        "the grant, whatever else is true.\n"
        "3. List the windows already committed in that territory, and say which "
        "periods are free.\n"
        "4. Name the agreement each blocking licence sits under, so the answer "
        "can be checked against the paper.\n\n"
        "If the licence data is ambiguous, say so rather than resolving it."
    )
# endregion: clearance_check


@mcp.prompt(
    name="window_review",
    description="Review the licence windows on a title for gaps and overlaps.",
)
def window_review(title_id: str) -> str:
    """A review, not a lookup: the model is being asked to find the problems."""
    return (
        f"Review the licence windows on {title_id}.\n\n"
        "Report, in this order:\n"
        "- overlapping exclusives in the same territory and right — these are "
        "contract breaches, list them first;\n"
        "- territories where an active window ends within 90 days;\n"
        "- territories with no coverage at all.\n\n"
        "Give counts before examples, and quote licence identifiers so each "
        "finding can be checked. If a title carries more licences than you can "
        "review carefully, say how many there are and ask which territories "
        "matter rather than skimming all of them."
    )
