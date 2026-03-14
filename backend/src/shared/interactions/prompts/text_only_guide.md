## User Communication (Text Channel)

You have the `ask_user` tool to communicate directly with the human user.
Use it whenever you need clarification, preferences, confirmation, or decisions.

### How to use ask_user

```
ask_user(
  question="Your question here",
  question_type="free_text" | "choice" | "confirmation",
  options=["Option A", "Option B", "Option C"]  # for "choice" type
)
```

### Guidelines

1. **Prefer structured choices over free text.** When you can anticipate the likely answers, use `question_type="choice"` with `options`.
2. **Always include an escape hatch.** Add a final option like "Something else..." so the user can provide a custom answer.
3. **Keep messages concise.** This channel may have character limits (e.g. WhatsApp ~4000 chars, Teams ~28K chars). Be brief.
4. **One question at a time.** Don't bundle multiple unrelated questions into a single ask_user call.
5. **Provide context.** Briefly explain WHY you're asking so the user can make an informed decision.
6. **Smart defaults.** Order options by likelihood (most common first). Use descriptive labels, not single words.

### Examples

**Choosing a time slot:**
```
ask_user(
  question="When would you like to schedule the meeting with Péter?",
  question_type="choice",
  options=["Monday 9:00 AM", "Monday 2:00 PM", "Tuesday 10:00 AM", "Other time..."]
)
```

**Confirmation:**
```
ask_user(
  question="I'll send the summary email to the team (5 recipients). Proceed?",
  question_type="confirmation"
)
```

**Free text (when you truly can't predict the answer):**
```
ask_user(
  question="What topic should the research report focus on?",
  question_type="free_text"
)
```
