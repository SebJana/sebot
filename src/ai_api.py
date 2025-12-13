import os
from openai import OpenAI
from dotenv import load_dotenv
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

client = OpenAI(api_key=OPENAI_API_KEY)

router_system_prompt = '''
You are an assistant router. For each user request:

1. Correct any obvious grammar or spelling mistakes.
   - If the text did not need correction, set "corrected_text" to "unchanged".
2. Identify the user's intent/task and assign a category. Example categories:
   - smart_home: controlling devices, lights, thermostat, alarms
   - chat: casual conversation, jokes, greetings
   - question: factual questions, general knowledge
   - web_search: current events, unknown facts, real-time information
   - web_search_with_wiki: topics where Wikipedia is likely a strong primary source
   - translation: translating text between languages
   - reminder: timers, alarms, calendar events
   - media_control: playing music, videos, podcasts
   - other: anything that doesn't fit above categories
3. Decide which tool should handle it:
   - "action" → if it can be executed directly (like turn_on_light, set_timer, play_music)
   - "llm" → if it needs reasoning, knowledge, or conversation

Output in strict JSON (no extra text):

{
  "corrected_text": "<user text corrected or 'unchanged'>",
  "intent": {
      "category": "<intent category>",
      "description": "<short description of user's task>"
  },
  "tool": "<'action' or 'llm'>",
  "action": "<optional action name if tool is 'action'>"
}

Rules:
- Only modify "corrected_text" if needed; otherwise use "unchanged".
- Use "web_search" intent if the request requires looking up current or unknown information.
- For "web_search" let the description be the prompt to web search the needed information, so don't add "find", just the actual search    prompt.
- Decide whether a Wikipedia search would be beneficial.
- Properly evaluate if a web search is needed or if the LLM itself contains that information in it's knowledge.
- Always respond in valid JSON only. Do not include any commentary or additional fields.
'''

# TODO provide tools that can be used like get_weather(), get_nfl_schedule(), get_joke(), get_waste_collection_schedule()
# Some tasks don't need the LLM so add another tool choice: basic
def classification(prompt: str):
    response = client.responses.create(
        model="gpt-5-nano",
        input=[
            {"role": "system", "content": router_system_prompt},
            {"role": "user", "content": prompt}
        ]
    )

    return response.output_text
