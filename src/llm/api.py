import os
from openai import OpenAI
import json
from dotenv import load_dotenv
from .system_prompt import router_system_prompt, conversation_system_prompt
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

client = OpenAI(api_key=OPENAI_API_KEY)

# TODO add conversation history for last X prompts and answers

# TODO provide tools that can be used like get_weather(), get_nfl_schedule(), get_joke(), get_waste_collection_schedule()
# Some tasks don't need the LLM so add another tool choice: basic, if tool resulted in full text output
def classification(prompt: str):
    response = client.responses.create(
        model="gpt-5-nano",
        input=[
            {"role": "system", "content": router_system_prompt},
            {"role": "user", "content": prompt}
        ]
    )

    return response.output_text


def conversation(prompt: str, additional_data=None):
    """Run a conversational LLM call using `conversation_system_prompt`.

    If `additional_data` is provided it will be included as an extra system
    context message so the model can use it when producing the reply.
    ``additional_data`` should be a JSON-serializable object (dict/list).
    """

    # Build messages: system prompt first
    messages = [
        {"role": "system", "content": conversation_system_prompt}
    ]

    # Attach additional data as a system-level context block if provided.
    # Keep it compact JSON to avoid ambiguity.
    if additional_data is not None:
        try:
            additional_json = json.dumps(additional_data, ensure_ascii=False)
        except Exception:
            additional_json = str(additional_data)
        messages.append({"role": "system", "content": "Additional data:\n" + additional_json})

    # Then the user message
    messages.append({"role": "user", "content": prompt})

    response = client.responses.create(
        model="gpt-5-mini",
        input=messages
    )

    return response.output_text