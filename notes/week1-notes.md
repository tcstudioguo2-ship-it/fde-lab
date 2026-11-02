# Week 1 notes — Tool Use loop (2026-10-26)
- Agent loop = model returns a tool_call → code executes the tool → result returned as role:"tool" with tool_call_id → model decides again or gives the final answer. History is maintained manually (practice 2); the week-2 kernel runs non-streaming to avoid practice 3's split-word spacing loss.
- JSON (practice 4): output parsed cleanly with all 5 fields, but values were literal — "tomorrow" did not become a real date and "3pm" did not become 15:00. Date normalisation must be program-side in week 2; never store the raw text in the calendar.
- Tool calling (practice 5): get_weather(Shenzhen) → 28C cloudy, full decide → call → feed back → decide loop verified on the Zhipu compatible interface. Week-2 concierge kernel reuses this skeleton; calendar/mail/todo start as stubs, swapped to real implementations one at a time.
- Course status: 《Building with the Claude API》 completed on 2026-10-29.
