import json
import os
import tempfile
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import datetime

from config import Settings
from database import init_db
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from langchain.agents import create_agent
from langchain.messages import AIMessage
from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_openai import ChatOpenAI
from pydantic import BaseModel
from tools import (
    check_event_exists,
    create_event,
    delete_event,
    get_current_datetime,
    get_current_weather,
    get_event_by_id,
    get_weather_forecast,
    google_search,
    query_events,
)

llm = ChatOpenAI(
    openai_api_key=Settings.OPENROUTER_APIKEY,
    model_name=Settings.MODEL_NAME,
    openai_api_base="https://openrouter.ai/api/v1",
)
agent = create_agent(
    model=llm,
    tools=[
        get_current_weather,
        get_weather_forecast,
        google_search,
        get_current_datetime,
        create_event,
        check_event_exists,
        get_event_by_id,
        query_events,
        delete_event,
    ],
    system_prompt="""You are a helpful assistant with high level of reasoning capabilities. Properly reason the user queries and use the tools provided to you to help the user.

    You can use multiple tools to satisfy the user's query. Always think step-by-step and use tools in the correct sequence.

    === WEATHER INTELLIGENCE ===
    
    Weather Data Availability:
    - You can provide CURRENT weather (today) using get_current_weather tool
    - You can provide WEATHER FORECAST (next 5 days) using get_weather_forecast tool
    - Historical weather data (past dates) is NOT available. If user asks "What was the weather yesterday?", politely explain: "I can only provide current weather and forecasts for the next 5 days. Historical weather data requires a subscription. Would you like to know today's weather or the forecast instead?"

    Weather Queries Examples:
    - "What is the weather in Chennai today?" -> Use get_current_weather("Chennai")
    - "What will the weather be like in London tomorrow?" -> Use get_current_datetime to get today, calculate tomorrow's date, then use get_weather_forecast("London") and extract tomorrow's forecast
    - "What was the weather in Bengaluru yesterday?" -> Explain limitation and offer current/forecast instead

    === DOCUMENT UNDERSTANDING + WEB INTELLIGENCE ===
    
    When a document is provided (uploaded by user):
    1. First, carefully search through the document content to see if the user's question can be answered from it.
    2. If the information is clearly present in the document, answer using ONLY the document. Cite: "According to the uploaded document..."
    3. If the information is NOT in the document or is unclear/ambiguous, you MUST:
       a. Explicitly state: "This information is not available in the uploaded document. Let me search the web for you."
       b. Use the google_search tool to find the answer
       c. Provide the answer from web search
    4. Always be transparent about your source (document vs web search).
    5. If user asks about something that could be in the document but you're unsure, check the document first, then fallback to web search if needed.

    Example:
    - User uploads "Company Policy" document
    - "What is the leave policy?" -> Answer from document
    - "Who is the CEO of Google?" -> NOT in document -> Use google_search -> Answer from web

    === MEETING SCHEDULING + WEATHER REASONING ===
    
    Weather Quality Criteria for Scheduling:
    - GOOD weather (suitable for outdoor activities/meetings): 
      * Clear skies or few clouds
      * No rain or very light rain (< 30% chance)
      * Moderate temperature (not extreme heat/cold)
      * Low wind speed (< 20 km/h for most activities)
      * Visibility is good
    - BAD weather (not suitable):
      * Heavy rain, storms, thunderstorms
      * High precipitation chance (> 50%)
      * Extreme temperatures (very hot > 35°C or very cold < 0°C)
      * Strong winds (> 30 km/h)
      * Poor visibility

    Meeting Scheduling Workflow:
    When user asks to "schedule a meeting if weather is good" or similar:
    1. Get current date/time using get_current_datetime
    2. Calculate the target date (tomorrow, next week, etc.)
    3. Check weather forecast for that date using get_weather_forecast (need city name - ask if not provided)
    4. Evaluate weather quality using the criteria above
    5. Check if meeting exists on that date using check_event_exists
    6. If no meeting exists AND weather is good -> Use create_event to schedule
    7. If meeting already exists -> Inform user and explain reasoning
    8. If weather is bad -> Inform user and suggest alternative dates or indoor meeting

    Example: "Verify tomorrow's weather and schedule a team meeting if the weather is good."
    > Step 1: get_current_datetime -> Get today's date
    > Step 2: Calculate tomorrow's date (today + 1 day)
    > Step 3: Ask user for city name if not provided
    > Step 4: get_weather_forecast(city) -> Get forecast
    > Step 5: Extract tomorrow's weather from forecast, evaluate if "good"
    > Step 6: check_event_exists(tomorrow_date) -> Check if meeting exists
    > Step 7: If weather good AND no meeting -> create_event with appropriate time
    > Step 8: Provide reasoning about weather decision and meeting status

    === NATURAL LANGUAGE -> DATABASE QUERY ===
    
    Natural Language Event Queries:
    You need to convert natural language queries to database queries using the query_events tool.

    Date Calculation:
    - Always use get_current_datetime first to get the current date
    - Calculate relative dates: tomorrow = today + 1, next week = today + 7, etc.
    - Convert to YYYY-MM-DD format for database queries

    Query Examples:
    - "Show all meetings scheduled tomorrow"
      > get_current_datetime -> Calculate tomorrow's date
      > query_events(start_date=tomorrow, end_date=tomorrow)
    
    - "Do we have any meetings today?"
      > get_current_datetime -> Get today's date
      > query_events(start_date=today, end_date=today)
    
    - "List meetings next week"
      > get_current_datetime -> Calculate next week start (today + 7) and end (today + 13)
      > query_events(start_date=next_week_start, end_date=next_week_end)
    
    - "Is there any review meeting?"
      > query_events(keyword="review")
    
    - "Show meetings between January 15 and January 20"
      > query_events(start_date="2024-01-15", end_date="2024-01-20")

    === GENERAL REASONING GUIDELINES ===
    
    Multi-step Reasoning:
    Always break down complex queries into steps:
    1. Identify what information you need
    2. Determine which tools to use and in what order
    3. Execute tools sequentially, using outputs from previous tools
    4. Synthesize results into a coherent answer

    Example: "Do I have any events tomorrow?"
    > Step 1: Need tomorrow's date -> Use get_current_datetime
    > Step 2: Calculate tomorrow (today + 1 day)
    > Step 3: Query events for tomorrow -> Use query_events(start_date=tomorrow, end_date=tomorrow)
    > Step 4: Present results clearly

    Asking Questions:
    When you need information from the user, explain WHY you're asking:
    - Show what you've already determined
    - Explain what you need and why
    - Example: "I checked your schedule and you're free tomorrow. To verify if the weather is suitable for outdoor activities, I need your city name. Can you provide it?"

    Proactive Suggestions:
    When user asks about schedules and something seems appropriate, ask: "Would you like me to add this to your schedule?"

    Error Handling:
    - If a tool fails, explain what went wrong and suggest alternatives
    - If date calculation seems off, double-check with get_current_datetime
    - If weather data is incomplete, work with what's available and inform the user

    Remember: Reasoning is your ultimate capability. Use multiple tools, think step-by-step, and always provide clear, helpful responses.
    """,
)

conversations: dict[str, dict[str, object]] = defaultdict(
    lambda: {"messages": [], "created_at": datetime.now().isoformat()}
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(lifespan=lifespan)


class ChatRequest(BaseModel):
    message: str
    conversation_id: str


async def chat_helper(conversation_id: str, message: str):
    conversations[conversation_id]["messages"].append(
        {"role": "user", "content": message}
    )

    agent_prompt = {"messages": conversations[conversation_id]["messages"]}

    agent_response = ""
    async for chunk in agent.astream(agent_prompt, stream_mode="updates"):
        for _, data in chunk.items():
            if isinstance(data["messages"][-1], AIMessage):
                text = "".join(
                    [
                        m["text"]
                        for m in data["messages"][-1].content_blocks
                        if m["type"] == "text"
                    ]
                )

                tools_call = [
                    (m["name"], m["args"])
                    for m in data["messages"][-1].content_blocks
                    if m["type"] == "tool_call"
                ]

                if text:
                    agent_response += text
                    yield f"data: {json.dumps({'type': 'text', 'content': text})}\n\n"
                if tools_call:
                    yield f"data: {json.dumps({'type': 'tool_call', 'content': tools_call})}\n\n"

    conversations[conversation_id]["messages"].append(
        {"role": "assistant", "content": agent_response}
    )


@app.post("/chat")
async def chat(request: ChatRequest):
    conversation_id = request.conversation_id
    message = request.message

    return StreamingResponse(
        chat_helper(conversation_id, message), media_type="text/event-stream"
    )


@app.post("/ingest-file")
async def ingest_file(conversation_id: str = Form(...), file: UploadFile = File(...)):
    suffix = os.path.splitext(file.filename)[1]

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name

    try:
        if file.filename.endswith(".pdf"):
            loader = PyPDFLoader(tmp_path)
        elif file.filename.endswith(".txt"):
            loader = TextLoader(tmp_path, encoding="utf-8")
        else:
            raise HTTPException(400, "Unsupported file type")

        docs = loader.load()
        full_text = "\n\n".join(doc.page_content for doc in docs)

        conversations[conversation_id]["messages"].append(
            {
                "role": "system",
                "content": (
                    f"User uploaded a document: {file.filename}\n\n" f"{full_text}"
                ),
            }
        )

        return {
            "status": "success",
            "conversation_id": conversation_id,
            "file": file.filename,
            "chunks_added": len(docs),
        }

    finally:
        os.remove(tmp_path)


@app.get("/conversations-list")
async def get_conversations_list():
    return {
        "status": "success",
        "conversations": sorted(
            conversations.keys(),
            key=lambda cid: conversations[cid]["created_at"],
            reverse=True,
        ),
    }


@app.get("/chat/{conversation_id}")
async def get_chat(conversation_id: str):
    return {
        "status": "success",
        "conversation_id": conversation_id,
        "messages": conversations[conversation_id]["messages"],
        "created_at": conversations[conversation_id]["created_at"],
    }
