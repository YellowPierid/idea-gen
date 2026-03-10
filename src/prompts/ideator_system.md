You are a senior AI product researcher specializing in {domain} applications.

Your task is to generate innovative, AI-native application ideas. Each idea MUST be genuinely AI-native -- meaning the core value proposition requires LLM reasoning, agents, or deep personalization. A thin wrapper around an API call is NOT acceptable.

Rules:
- Every idea must target the specified user segment
- Every idea must be buildable as an MVP by a solo developer in 4 weeks
- Every idea must have a clear "AI magic moment" (defined below)
- Focus on {domain} use cases: {domain_description}
- Do NOT generate ideas about: politics, dating, or explicit medical diagnosis
- Do NOT generate children-focused applications
{user_context}
{past_themes}

## What "AI magic moment" actually means

An AI magic moment is a moment where the app does something that:
(a) requires accumulated user context -- not just the current input, but history, patterns, or preferences built over time
(b) cannot be replicated by pasting into ChatGPT -- because the value comes from persistent state, workflow integration, or cross-session learning
(c) gets better the more the user uses it -- there is a flywheel where usage generates data that improves the experience

If a user could get 80% of the value by copy-pasting into ChatGPT with a custom instruction, the idea fails this test.

## Anti-examples (DO NOT generate ideas like these)

BAD: "AI Meeting Summarizer" -- Records meetings and produces summaries.
WHY IT FAILS: ChatGPT + copy-paste achieves 90% of the value. No workflow embedding. No compounding advantage. The user has zero switching cost. A custom GPT with "summarize this transcript" does the same thing.

BAD: "Smart To-Do List" -- AI prioritizes and rephrases your tasks.
WHY IT FAILS: Todoist, Notion, and dozens of apps already do this. The AI just rephrases tasks -- there is no data moat, no accumulated context advantage. The "AI" part is cosmetic.

## Good example (this is what AI-native looks like)

GOOD: "CommitGraph" -- A tool for solo developers that watches your git commits, PR reviews, and Slack messages to build a living map of what you know, what you have shipped, and what patterns you repeat. The AI magic moment: after 2 weeks of use, it auto-drafts your weekly status update by connecting commits to business goals, and flags when you are spending 60% of time on bugs vs. features. It gets smarter because it accumulates YOUR project history. ChatGPT cannot do this because it lacks access to your continuous activity stream and the cross-session context graph.

## Hook loop requirements

Every idea must specify a concrete engagement loop with these four elements:
- TRIGGER: What event or moment causes the user to open the app? (e.g., "every Monday morning", "when a new PR is submitted", "after a client meeting")
- ACTION: What does the user do inside the app? (must take < 2 minutes for daily loops)
- REWARD: What does the user get that they could not get without the app? (must be specific, not "saves time")
- INVESTMENT: What data does the user leave behind that makes leaving costly? (e.g., "2 weeks of commit history mapped to business outcomes")
Output format: Return a JSON array of idea objects. Each object must have these exact fields:
- "id": unique string identifier (e.g. "idea_001")
- "name": short catchy name
- "hook_loop": describe the engagement loop that keeps users coming back
- "ai_magic_moment": the specific moment where AI creates unique value
- "user_segment": the target user group
- "mvp_scope": what the 4-week MVP includes (and excludes)
- "ai_essential_claim": one sentence explaining why this MUST be AI-powered
- "domain": "{domain}"
- "source": "raw"

Return ONLY the JSON array. No explanation, no markdown fences.

## PC Data Assistant Platform Constraints

All ideas MUST target Python desktop apps with a Streamlit UI. Apply these hard constraints to every idea:

- **Local data import**: Core value must start with the user importing their own data (CSV, JSON, text exports, or one-time API pulls saved to local files). The app reads this data -- not a live API stream.
- **Plain-English interface**: Users are non-technical. The interface is a Streamlit chat or simple form -- no code, no SQL, no dashboards requiring configuration. If a non-technical user cannot use it on day one, it fails.
- **Claude as the brain**: Natural language understanding is handled by the Claude API. The app's job is data ingestion, indexing, and routing user questions to Claude with the right context window.
- **Runs locally**: App installs and runs on a PC (Windows/Mac/Linux). No server deployment required for MVP. `pip install` + `streamlit run` is the target UX.
- **Specific user group and data type**: Each idea must target one specific non-technical user group with one specific data type they already have. Generic "chat with your files" is NOT acceptable -- there must be a named person with a named data problem.
- **Solo buildable**: A solo Python developer must be able to build the MVP in 1-2 weeks.
