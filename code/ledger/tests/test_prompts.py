"""Prompts carry a method, not just a wording.

These tests are unusual and deliberately so: they assert on the *content* of
generated text. That is defensible here because the value of a prompt is the
procedure it encodes, and a procedure that quietly loses a step is a regression
even though nothing raises.
"""

from __future__ import annotations

import pytest
from mcp.shared.exceptions import MCPError


async def test_both_prompts_are_offered(client):
    async with client:
        assert {p.name for p in await client.list_prompts()} == {
            "clearance_check",
            "window_review",
        }


async def test_clearance_check_puts_exclusivity_before_availability(client):
    async with client:
        result = await client.get_prompt(
            "clearance_check",
            {"title": "The Winter Cartograph", "territory": "GB", "rights": "svod"},
        )
    text = result.messages[0].content.text

    assert "GB" in text and "svod" in text
    assert text.index("exclusive") < text.index("windows already committed"), (
        "checking availability before exclusivity is how you clear something "
        "that is already sold"
    )


async def test_clearance_check_refuses_to_guess_the_title(client):
    async with client:
        result = await client.get_prompt(
            "clearance_check", {"title": "The", "territory": "US"}
        )
    assert "do not guess" in result.messages[0].content.text


async def test_window_review_tells_the_model_what_to_do_when_there_is_too_much(client):
    async with client:
        result = await client.get_prompt("window_review", {"title_id": "T-1152"})
    text = result.messages[0].content.text
    assert "ask which territories" in text, (
        "a title with 180 licences must not be skimmed silently"
    )


async def test_a_prompt_needs_its_arguments(client):
    async with client:
        with pytest.raises(MCPError, match="Missing required arguments"):
            await client.get_prompt("clearance_check", {})
