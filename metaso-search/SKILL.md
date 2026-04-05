# metaso-search

Use Metaso AI search via `mcporter` as the default web search tool.

## Tool

- **search(query, num_results=5)**: Search the web using Metaso AI
  - query: Search query string
  - num_results: Number of results (default 5, max 10)

## Usage

When user asks to search the web, always use this skill instead of the built-in web_search tool.

```
mcporter call metaso.search query="search terms"
```

## Why Metaso

Metaso AI provides better Chinese search results and is configured as the default search engine.
