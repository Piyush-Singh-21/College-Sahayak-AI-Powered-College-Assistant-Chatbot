import os
import google.generativeai as genai
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configure the Gemini API
try:
    genai.configure(api_key=os.getenv("PMAK-68c85cfda4d2520001ab4093-c8af7e04e561867cea2792859d1139ac32"))
    generation_model = genai.GenerativeModel('gemini-pro')
except Exception as e:
    print(f"Error configuring Google AI: {e}")
    generation_model = None

# --- Simplified Knowledge Base ---
# In a real app, this would be loaded from your processed PDFs/FAQs.
KNOWLEDGE_BASE = """
Document 1: The deadline for tuition fee payment for the autumn semester is October 15, 2025. A late fee of ₹500 will be applied after this date. Payments can be made online via the student portal.
Document 2: The 'Innovator's Scholarship' application form is available in the Dean's office. The last day to submit the form is September 30, 2025. To be eligible, students must have a GPA above 8.5 and no backlogs.
Document 3: The mid-semester examination timetable is posted on the notice board near the library. Exams for computer science students are scheduled from September 22 to September 26, 2025.
"""

# --- FastAPI App Setup ---
app = FastAPI()

# Allow requests from your frontend (CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

class ChatRequest(BaseModel):
    message: str

@app.get("/")
def read_root():
    return {"status": "Campus Chatbot API is running."}

@app.post("/chat")
async def handle_chat(request: ChatRequest):
    if not generation_model:
        return {"reply": "Error: The AI model is not configured. Please check the API key."}

    user_query = request.message

    # This is the core of the RAG approach
    prompt = f"""
    You are a helpful college assistant chatbot. Your name is 'CampusBot'.
    Answer the user's question based ONLY on the information provided in the following Knowledge Base.
    If the answer is not in the knowledge base, say "I'm sorry, I don't have that information. Please contact the administration office for details."

    ---
    Knowledge Base:
    {KNOWLEDGE_BASE}
    ---

    User's Question:
    "{user_query}"
    """

    try:
        # Generate the response from the model
        response = generation_model.generate_content(prompt)
        bot_reply = response.text
    except Exception as e:
        print(f"Error generating response: {e}")
        bot_reply = "Sorry, I encountered an error while processing your request."

    return {"reply": bot_reply}