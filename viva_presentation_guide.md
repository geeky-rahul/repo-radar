# 🎯 RepoRadar: Viva & Presentation Guide

This document is designed to help you quickly review the core concepts, architecture, and theoretical aspects of RepoRadar for your presentation and viva.

---

## 📌 1. The "Elevator Pitch" (Core Summary)

> **What is RepoRadar?**  
> An AI-powered GitHub repository search and discovery platform that translates natural language queries into optimized searches and ranks repositories based on actual health and utility, not just keyword frequency.

**The Problem it Solves:**
Traditional GitHub search relies on lexical (keyword) matching. A query like *"best beginner python chatbot"* returns repos merely because they contain those words. It often surfaces "abandonware"—projects with high stars that haven't been updated in years.

**The Solution:**
1. **Semantic Parsing:** Uses an LLM (Google Gemini) via LangChain to understand user intent and translate it into strict GitHub API constraints.
2. **Composite Ranking Engine:** Scores repositories using a multi-dimensional mathematical formula (stars, recency, completeness, activity, health, trend) to prioritize high-quality, maintained projects.

---

## 🏗️ 2. Architecture & Technology Stack (Key Theory)

Be prepared to explain *why* you chose these specific technologies:

*   **Backend Framework:** **FastAPI (Python 3.12+)** 
    *   *Why?* Native `async/await` support is essential since the app heavily relies on non-blocking I/O (calling GitHub, Gemini, and Redis). It also provides automatic API documentation and Pydantic validation.
*   **LLM Orchestration:** **LangChain (LCEL)** 
    *   *Why?* Provides a clean, declarative pipeline (`prompt | llm | parser`) to guarantee the LLM outputs strict, parseable JSON rather than raw text.
*   **AI Model:** **Google Gemini 1.5 Flash** 
    *   *Why?* Offers low latency and high accuracy for JSON structuring at a very low operational cost.
*   **Caching & State:** **Redis (Async)** 
    *   *Why?* Drastically reduces GitHub API load and response times. Distributed caching allows multiple server workers to share the same cache.
*   **Authentication:** **Google OAuth 2.0**
    *   *Why?* Frictionless, secure delegated access without the overhead of managing custom passwords.

---

## 🧮 3. The Ranking Algorithm (Crucial Theory)

The most unique technical feature of this project is the **Composite Ranking Engine**. It assigns a score between `[0, 1]` to each repo.

**The Formula:**
`Score = 0.45(Stars) + 0.18(Recency) + 0.15(Completeness) + 0.10(Activity) + 0.08(Health) + 0.04(Trend)`

**Key Mathematical Concepts Used:**
1.  **Logarithmic Scaling for Stars:** `log1p(stars) / log1p(200_000)` 
    *   *Why?* Prevents outliers (e.g., a repo with 300k stars) from completely dominating the score. The difference between 10 stars and 1,000 stars is huge, but the difference between 100k and 150k is less significant.
2.  **Exponential Decay for Recency:** `exp(-days_since_push / 730)` 
    *   *Why?* Smoothly penalizes projects over a 2-year (730 days) period. A project updated yesterday gets nearly 100% for this metric; one updated 3 years ago drops to near zero. This effectively filters out dead projects.

---

## ❓ 4. Frequently Asked Questions (Viva Preparation)

Here are the most likely questions an examiner will ask, along with strong technical answers.

> [!IMPORTANT]
> Focus on the *reasoning* behind your technical choices. Examiners care more about "Why did you do this?" than "How did you write the code?"

### Q1: How does your search differ from native GitHub search?
**Answer:** GitHub search uses ElasticSearch for lexical matching (finding exact keywords). If I search "framework for microservices", GitHub looks for those literal words. RepoRadar uses an LLM to understand the *semantic intent*, mapping it to API qualifiers like `language:go` or `topic:microservices`. More importantly, it re-ranks the results using our custom health score, whereas GitHub natively sorts purely by "Best Match" (keyword density) or raw stars.

### Q2: How does the system handle GitHub API rate limits?
**Answer:** GitHub strictly limits API requests (10/min for unauthenticated, 5000/hr for authenticated). We mitigate this in two ways:
1. We use a GitHub Personal Access Token to raise our limit.
2. We implemented a **Redis caching layer**. When a user searches, we hash the query. If it exists in Redis, we serve the cached JSON immediately. This drops response time from ~500ms down to <15ms and completely bypasses the GitHub API.

### Q3: What happens if the LLM (Gemini) fails or hits its own rate limit?
**Answer:** The system features a dual-layer parsing strategy for **graceful degradation**. If the LangChain pipeline throws an exception, the system catches it and routes the query to a deterministic, rule-based Regex Fallback Parser. It tries to extract basic constraints (like `language:python` or `stars:>100`) to ensure the user still gets results rather than a 500 Internal Server Error.

### Q4: Explain the Recency Score in your ranking algorithm. Why Exponential Decay?
**Answer:** Exponential decay is used to model the "half-life" of a repository's relevance. It ensures that the penalty for being unmaintained increases smoothly over time. We set the decay constant over roughly 2 years (`730 days`). This mathematical approach actively filters out "abandonware"—projects that historically gained thousands of stars but have since been abandoned by their maintainers.

### Q5: Why did you use Redis instead of just a Python Dictionary for caching?
**Answer:** While an in-memory dictionary works for a single worker thread, FastAPI is often deployed with multiple workers (e.g., using Uvicorn/Gunicorn). A Python dict is isolated to a single worker's memory. Redis acts as a centralized, distributed cache that all workers can access. Additionally, Redis handles TTL (Time-To-Live) expiration automatically and allows us to persist user state like favorites and collections.

### Q6: Can the system still function if Redis goes offline?
**Answer:** Yes, it is built with **fault tolerance**. If the connection to Redis fails, the cache service catches the `ConnectionError` and simply falls back to fetching data live via the LLM and GitHub APIs. Performance will degrade (slower response times), but the application will not crash.

### Q7: What is LCEL and why is it useful here?
**Answer:** LCEL stands for LangChain Expression Language. It allows us to define our AI pipeline cleanly as `prompt | llm | parser`. We needed this because getting raw text from an LLM is useless for an API integration. By using LCEL with a `PydanticOutputParser`, we force the LLM to return a strictly formatted JSON object that maps perfectly to our Python `ParsedGitHubQuery` schema.

### Q8: What would be the next step to improve this project? (Future Scope)
**Answer:** The most logical next step would be implementing true **Semantic Vector Search**. Instead of relying on GitHub's text search at all, we could embed repository READMEs into vector embeddings and store them in a Vector Database (like Pinecone). This would allow for exact conceptual matching rather than relying on GitHub's API filters.
