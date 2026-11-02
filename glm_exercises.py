"""
FDE Week 1 - Claude Academy "Building with the Claude API", GLM edition.

Maps the first four modules' hands-on exercises to Zhipu GLM
(OpenAI-compatible endpoint). Only needs the `openai` package.

Usage (PowerShell, with .venv activated):
    $env:ZHIPU_API_KEY="your-key"   # env var only, never in code
    python glm_exercises.py [1-6]    # no arg = run all

Model: glm-4-flash (free tier, good enough for practice)
"""

import json
import os
import sys

from openai import OpenAI

client = OpenAI(
    api_key=os.environ.get("ZHIPU_API_KEY"),
    base_url="https://open.bigmodel.cn/api/paas/v4/",
)
MODEL = "glm-4-flash"


def need_key():
    if not os.environ.get("ZHIPU_API_KEY"):
        print("Missing env var ZHIPU_API_KEY - set it in PowerShell first")
        sys.exit(1)


def ex1_system_prompt():
    "Exercise 1: system prompt (module: Accessing Claude with the API)"
    print("\n=== Ex1: system prompt ===")
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": "You are a minimalist assistant who answers in one sentence only."},
            {"role": "user", "content": "Introduce Beijing"},
        ],
    )
    print(resp.choices[0].message.content)


def ex2_multiturn():
    "Exercise 2: multi-turn history management (module: Accessing Claude with the API)"
    print("\n=== Ex2: multi-turn, history maintained by us ===")
    history = [
        {"role": "system", "content": "You are an assistant with a good memory."},
        {"role": "user", "content": "My name is Guo, I do pre-sales in Shenzhen."},
    ]
    r1 = client.chat.completions.create(model=MODEL, messages=history)
    history.append({"role": "assistant", "content": r1.choices[0].message.content})
    history.append({"role": "user", "content": "What is my name and where do I work?"})
    r2 = client.chat.completions.create(model=MODEL, messages=history)
    print(r2.choices[0].message.content)
    print("(history now holds %d messages - the seed of Agent memory)" % len(history))


def ex3_streaming():
    "Exercise 3: streaming output (module: Accessing Claude with the API)"
    print("\n=== Ex3: streaming ===")
    stream = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": "Introduce Shenzhen in three sentences"}],
        stream=True,
    )
    for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            print(delta, end="", flush=True)
    print()


def ex4_structured():
    "Exercise 4: JSON structured output (module: Accessing Claude with the API)"
    print("\n=== Ex4: JSON structured output ===")
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "user",
                "content": "Parse into JSON: 'Meeting Lao Wang tomorrow 3pm in Nanshan about pricing'. "
                "Return JSON only, fields: date, time, person, place, topic",
            }
        ],
        response_format={"type": "json_object"},
    )
    data = json.loads(resp.choices[0].message.content)
    print(json.dumps(data, ensure_ascii=False, indent=2))
    print("(this is how the week-2 concierge agent will parse schedules)")


def get_weather(city):
    "Demo tool: weather lookup (fake data - the call flow is the point)"
    fake = {"Shenzhen": "28C cloudy", "Beijing": "12C sunny"}
    return fake.get(city, "unknown city")


def ex5_tool_use():
    "Exercise 5: tool calling = mini Agent loop (module: Tool use with Claude)"
    print("\n=== Ex5: tool calling = mini Agent loop ===")
    tools = [
        {
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Look up the current weather for a city",
                "parameters": {
                    "type": "object",
                    "properties": {"city": {"type": "string", "description": "City name"}},
                    "required": ["city"],
                },
            },
        }
    ]
    messages = [{"role": "user", "content": "How is the weather in Shenzhen today? Good for running?"}]

    # Step 1: model decides -> returns tool_call
    r1 = client.chat.completions.create(model=MODEL, messages=messages, tools=tools)
    msg = r1.choices[0].message
    messages.append(msg)

    # Step 2: execute tool -> feed result back
    for call in msg.tool_calls or []:
        args = json.loads(call.function.arguments)
        result = get_weather(**args)
        print("  [tool executed] get_weather(%s) -> %s" % (args, result))
        messages.append({"role": "tool", "tool_call_id": call.id, "content": result})

    # Step 3: model decides again with tool results -> final answer
    r2 = client.chat.completions.create(model=MODEL, messages=messages)
    print("  [final answer]", r2.choices[0].message.content)
    print("(decide -> call -> feed back -> decide = the skeleton of the week-2 hand-written Agent loop)")


DOC = (
    "Shenzhen Metro Line 14 connects Futian CBD with Pingshan, opened 2022.\n"
    "Shenzhen Metro Line 16 connects Dayun with Tianxin, opened 2022.\n"
    "Guangzhou-Shenzhen intercity rail links Guangzhou East with Shenzhen, about 1 hour.\n"
    "Shenzhen North is the high-speed rail hub, direct to Beijing, Shanghai, Wuhan."
)


def simple_retrieve(query, top_k=2):
    "Dependency-free retrieval: rank by keyword hits (demo flow; production uses vectors/hybrid)"
    scored = [(sum(1 for ch in query if ch in line), line) for line in DOC.split("\n")]
    scored.sort(reverse=True)
    return [line for _, line in scored[:top_k]]


def ex6_rag():
    "Exercise 6: RAG = retrieve + augmented generation (module: RAG and Agentic Search)"
    print("\n=== Ex6: RAG = retrieval + augmented generation ===")
    query = "Which Shenzhen metro line goes to Pingshan?"
    hits = simple_retrieve(query)
    print("  [retrieved]", hits)
    context = "\n".join(hits)
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "system",
                "content": "Answer ONLY from the [context] below. Say you don't know if it is not there.\n[context]\n" + context,
            },
            {"role": "user", "content": query},
        ],
    )
    print("  [augmented answer]", resp.choices[0].message.content)


EXERCISES = {
    "1": ex1_system_prompt,
    "2": ex2_multiturn,
    "3": ex3_streaming,
    "4": ex4_structured,
    "5": ex5_tool_use,
    "6": ex6_rag,
}

if __name__ == "__main__":
    need_key()
    picks = sys.argv[1:] if len(sys.argv) > 1 else sorted(EXERCISES)
    for p in picks:
        if p in EXERCISES:
            EXERCISES[p]()
    print("\nDone: core techniques from the Academy's first four modules, all running on GLM.")
