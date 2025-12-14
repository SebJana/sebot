"""
web_search.py

Lightweight web-search helpers used by the assistant.

Important notes / limitations:
- This module intentionally does NOT perform full-page web scraping. It only
    collects small, structured pieces of information: search result titles,
    URLs and short snippets from DuckDuckGo (via the DDGS package), and a short
    excerpt from the top Wikipedia page for a query.
- Reasons for the limitation:
    1) Token and context limits: Sending full page contents to the downstream
         language model would consume a large number of tokens and make prompt
         construction brittle and expensive.
    2) Time and performance: Downloading and processing full pages is slower
         and significantly increases latency for queries.
    3) Legal / privacy concerns: Full scraping and storing page contents can
         create copyright and privacy exposure. Extracting only titles/snippets
         and short Wikipedia excerpts reduces legal risk and keeps usage minimal.

Given those constraints, the helpers below provide small, developer-friendly
peeks into search results rather than complete page text. The snippet might not have the full answer,
but it always provides context and keywords closely related to your search.
For expected workload with bigger context requirement, consider adding a tool call for this task.
"""

from ddgs import DDGS
import wikipedia

def get_wikipedia_info(search_prompt):
    """Return a short excerpt from the top Wikipedia page for the prompt.

    Behaviour:
    - Uses the `wikipedia` package to search for the query and fetch the top
        result's page content.
    - Returns only the first ~2000 characters to keep the excerpt small and
        avoid sending large documents to downstream systems.
    - Any exception (no results, disambiguation, network error) results in an
        empty string so callers can handle absence of wiki text gracefully.
    """

    # Get search results (may be empty)
    results = wikipedia.search(search_prompt)

    try:
        # Fetch the top result's page content and return a short excerpt.
        # We deliberately slice the content to limit token usage downstream.
        page = wikipedia.page(results[0])
        return page.content[:2500]
    except Exception:
        # Return empty text upon any error (robust failure mode)
        return ""


def get_relevant_webtext(search_prompt, max_results=10):
    """Return a list of lightweight "peek" strings for search results.

    For each result we only keep:
    - Title
    - Short snippet/body provided by the DDGS search response

    This intentionally avoids fetching and returning full page HTML/text.
    """

    # DDGS.text returns an iterator/generator; request a limited number of
    # results to keep response size predictable.
    results = DDGS().text(search_prompt, max_results=max_results)

    relevant_text = []

    for r in results:
        # DDGS result is a small dict with keys like 'href', 'title', 'body'.
        # url = r.get('href')
        title = r.get("title", "")
        snippet = r.get("body", "")

        text = f"Title: {title}\nSnippet: {snippet}"
        relevant_text.append(text)

    return relevant_text


def run_web_search(prompt: str, category: str = "web_search", max_results: int = 15):
    """Run a lightweight web search and optionally a short Wikipedia lookup.

    Args:
        prompt (str): The search query string to run.
        category (str): Controls wiki lookup behavior. "web_search" (default)
            runs only the DuckDuckGo peek. "web_search_with_wiki" also fetches
            a short Wikipedia excerpt.
        max_results (int): Max number of DDGS results to collect.

    Returns:
        dict: A dict with keys:
            - "prompt" (str): The final search prompt used.
            - "wiki" (str): Short Wikipedia excerpt or empty string.
            - "results" (list[str]): Compact title/snippet strings from DDGS.
    """

    # Only run wiki search if specifically requested
    wiki_text = ""
    if category == "web_search_with_wiki":
        wiki_text = get_wikipedia_info(prompt)

    results = get_relevant_webtext(prompt, max_results=max_results)

    return {
        "prompt": prompt,
        "wiki": wiki_text,
        "results": results,
    }


# Example usage (kept here for demo / development only)
if __name__ == "__main__":
    res = run_web_search("NFL results last week")
    print(res.get("wiki"))
    print(res.get("results"))