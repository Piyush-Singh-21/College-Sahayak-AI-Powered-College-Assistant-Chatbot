import os
import uuid
from flask import Flask, request, jsonify, render_template_string
import google.generativeai as genai
import firebase_admin
from firebase_admin import credentials, firestore
from dotenv import load_dotenv

# --- INITIALIZATION ---

# Load environment variables from .env file
load_dotenv()

# Initialize Flask App
app = Flask(__name__)

# Configure Gemini API Key
# Make sure to set GEMINI_API_KEY in your .env file or environment variables
gemini_api_key = os.getenv("GEMINI_API_KEY")
import sys
if not gemini_api_key:
    print("Error: GEMINI_API_KEY not found. Please set it in your .env file or environment.")
    sys.exit(1)
genai.configure(api_key=gemini_api_key)

# Configure Firebase Admin SDK
# Set the GOOGLE_APPLICATION_CREDENTIALS environment variable to point to your service account key file.
try:
    # In a deployed environment, you might not use a file.
    # The environment variable is the standard way.
    cred = credentials.ApplicationDefault()
    firebase_admin.initialize_app(cred)
except Exception as e:
    print(f"Could not initialize Firebase Admin SDK. Did you set GOOGLE_APPLICATION_CREDENTIALS? Error: {e}")
    # Fallback for local development if the env var is not set, but the file exists.
    if os.path.exists('serviceAccountKey.json'):
        print("Found serviceAccountKey.json. Trying to initialize with it.")
        cred = credentials.Certificate('serviceAccountKey.json')
        firebase_admin.initialize_app(cred)
    else:
        print("Exiting: Firebase Admin SDK initialization failed.")
        exit(1)


db = firestore.client()

# This would be provided by the environment in the original example.
# For a standalone app, we can define it or get it from env.
APP_ID = os.getenv("APP_ID", "default-app-id")

# --- KNOWLEDGE BASE & AI PROMPT ---

knowledge_base = """
--- FAQs (Frequently Asked Questions) ---
Q: What is the deadline for fee payment for the current semester?
A: The deadline for tuition fee payment is September 30, 2025. A late fee of ₹500 will be applied after this date.

Q: How can I apply for scholarships?
A: Scholarship forms are available on the college website under the 'Announcements' section. The last date to submit the 'Merit-cum-Means' scholarship form is October 15, 2025.

Q: What are the library hours?
A: The library is open from 9:00 AM to 8:00 PM on weekdays and 10:00 AM to 4:00 PM on Saturdays. It is closed on Sundays and public holidays.

Q: When does the new semester start?
A: The upcoming semester (Odd Semester 2025) will commence on October 10, 2025. The detailed timetable will be released one week prior.

--- Documents & Circulars ---
Document Ref: #CIRCULAR_EXAM_2025
Content: The end-semester examinations are scheduled to begin from December 5, 2025. Examination forms must be filled and submitted online via the student portal by November 20, 2025. There will be no extension for form submission.

Document Ref: #HOSTEL_RULES_V3
Content: All hostel residents must return to the hostel premises by 10:00 PM. Special permission for late entry must be obtained from the warden in advance. Biometric attendance is mandatory upon entry and exit.

Document Ref: #ANTI_RAGGING_POLICY
Content: The institution has a zero-tolerance policy towards ragging. Any student found engaging in or abetting ragging will be subject to immediate disciplinary action, including suspension or expulsion, as per UGC regulations. Report incidents to the anti-ragging squad at help@ourcollege.edu.
"""

def get_system_prompt(language):
    return f"""You are a helpful, friendly, and accurate Campus Assistant chatbot for a college. Your primary goal is to answer student queries based *ONLY* on the information provided in the "Knowledge Base" section below.
    
    **Instructions:**
    1.  **Strictly Adhere to Context:** Do not use any external knowledge. If the answer is not in the Knowledge Base, politely state that you do not have information on that topic and suggest contacting the administration office.
    2.  **Be Conversational:** Respond in a clear, helpful, and natural tone.
    3.  **Language:** You MUST respond in {language}. The user's query will be in {language}, and your entire response must also be in {language}.
    4.  **Acknowledge Follow-ups:** If the user asks a follow-up question, understand the context from the previous turn.
    5.  **Be Concise:** Keep your answers to the point.

    **--- Knowledge Base ---**
    {knowledge_base}
    """

# --- HTML TEMPLATE ---

# The entire frontend is now served from this string by Flask.
# JavaScript has been modified to call the Flask backend endpoints.
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Campus Helper Chatbot (Python Backend)</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        body { font-family: 'Inter', sans-serif; }
        #chat-window::-webkit-scrollbar { width: 6px; }
        #chat-window::-webkit-scrollbar-track { background: #f1f5f9; }
        #chat-window::-webkit-scrollbar-thumb { background: #94a3b8; border-radius: 3px; }
        .message-bubble { transition: all 0.3s ease; transform: scale(0.95); opacity: 0; animation: popIn 0.3s forwards; }
        @keyframes popIn { to { transform: scale(1); opacity: 1; } }
        .dot-flashing { position: relative; width: 10px; height: 10px; border-radius: 5px; background-color: #475569; color: #475569; animation: dotFlashing 1s infinite linear alternate; animation-delay: .5s; }
        .dot-flashing::before, .dot-flashing::after { content: ''; display: inline-block; position: absolute; top: 0; }
        .dot-flashing::before { left: -15px; width: 10px; height: 10px; border-radius: 5px; background-color: #475569; animation: dotFlashing 1s infinite alternate; animation-delay: 0s; }
        .dot-flashing::after { left: 15px; width: 10px; height: 10px; border-radius: 5px; background-color: #475569; animation: dotFlashing 1s infinite alternate; animation-delay: 1s; }
        @keyframes dotFlashing { 0% { background-color: #475569; } 50%, 100% { background-color: #cbd5e1; } }
    </style>
</head>
<body class="bg-slate-100 flex items-center justify-center min-h-screen">
    <div class="w-full max-w-2xl mx-4 my-4 flex flex-col h-[95vh] bg-white rounded-2xl shadow-2xl">
        <header class="bg-slate-800 text-white p-4 rounded-t-2xl flex justify-between items-center shadow-md">
            <div>
                <h1 class="text-xl font-bold">Campus Helper</h1>
                <p class="text-sm text-slate-300">Your 24/7 college assistant</p>
            </div>
            <div class="flex items-center space-x-2">
                 <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="text-slate-400"><path d="m12 18-3.47-3.47a1 1 0 0 1 0-1.41l.53-.54a1 1 0 0 1 1.41 0L12 14.12l1.53-1.54a1 1 0 0 1 1.41 0l.53.54a1 1 0 0 1 0 1.41Z"/><path d="M12 22a10 10 0 1 1 0-20 10 10 0 0 1 0 20Z"/><path d="M18 6a1 1 0 1 0-2 0c0 1.1.9 2 2 2a1 1 0 0 0 0-2Z"/></svg>
                <select id="language-select" class="bg-slate-700 text-white text-sm rounded-md p-2 border-slate-600 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500">
                    <option value="English">English</option>
                    <option value="Hindi">हिन्दी (Hindi)</option>
                    <option value="Tamil">தமிழ் (Tamil)</option>
                    <option value="Telugu">తెలుగు (Telugu)</option>
                    <option value="Bengali">বাংলা (Bengali)</option>
                    <option value="Marathi">मराठी (Marathi)</option>
                </select>
            </div>
        </header>
        <main id="chat-window" class="flex-1 p-6 overflow-y-auto bg-slate-50"></main>
        <footer class="p-4 bg-white border-t border-slate-200 rounded-b-2xl">
            <form id="chat-form" class="flex items-center space-x-3">
                <input type="text" id="chat-input" placeholder="Ask about fees, deadlines, scholarships..." class="flex-1 w-full px-4 py-3 text-slate-800 bg-slate-100 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition" autocomplete="off">
                <button type="submit" id="send-button" class="bg-indigo-600 text-white rounded-lg p-3 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:bg-indigo-300 disabled:cursor-not-allowed transition-colors duration-300">
                    <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="22" y1="2" x2="11" y2="13"></line><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg>
                </button>
            </form>
        </footer>
    </div>
    <script>
        const chatWindow = document.getElementById('chat-window');
        const chatForm = document.getElementById('chat-form');
        const chatInput = document.getElementById('chat-input');
        const sendButton = document.getElementById('send-button');
        const languageSelect = document.getElementById('language-select');
        let isLoading = false;
        
        // Use localStorage to persist the user ID across sessions
        let userId = localStorage.getItem('chatbot_userId');
        if (!userId) {
            userId = crypto.randomUUID();
            localStorage.setItem('chatbot_userId', userId);
        }

        const addMessage = (sender, message) => {
            const messageElement = document.createElement('div');
            messageElement.classList.add('message-bubble', 'mb-4', 'max-w-lg');
            if (sender === 'user') {
                messageElement.classList.add('ml-auto', 'bg-indigo-600', 'text-white', 'rounded-xl', 'rounded-br-none');
                messageElement.innerHTML = `<p class="p-3">${message}</p>`;
            } else { // 'model' or 'loading'
                messageElement.classList.add('mr-auto', 'bg-slate-200', 'text-slate-800', 'rounded-xl', 'rounded-bl-none');
                if (message === 'loading') {
                    messageElement.id = 'loading-indicator';
                    messageElement.innerHTML = `<div class="p-4 flex items-center justify-center"><div class="dot-flashing"></div></div>`;
                } else {
                    // Basic markdown for bolding
                    const formattedMessage = message.replace(/\\*\\*([^*]+)\\*\\*/g, '<strong>$1</strong>').replace(/\\n/g, '<br>');
                    messageElement.innerHTML = `<div class="p-3">${formattedMessage}</div>`;
                }
            }
            chatWindow.appendChild(messageElement);
            chatWindow.scrollTop = chatWindow.scrollHeight;
        };

        const setUILoadingState = (loading) => {
            isLoading = loading;
            chatInput.disabled = loading;
            sendButton.disabled = loading;
            const loadingIndicator = document.getElementById('loading-indicator');
            if (loading) {
                if (!loadingIndicator) addMessage('model', 'loading');
            } else {
                if (loadingIndicator) loadingIndicator.remove();
            }
        };

        const getBotResponse = async (userMessage) => {
            setUILoadingState(true);
            try {
                const response = await fetch('/chat', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        message: userMessage,
                        language: languageSelect.value,
                        userId: userId
                    })
                });
                if (!response.ok) {
                    throw new Error(`Server error: ${response.status}`);
                }
                const data = await response.json();
                addMessage('model', data.reply);
            } catch (error) {
                console.error("Failed to get bot response:", error);
                addMessage('model', "Sorry, I couldn't connect to the server. Please try again.");
            } finally {
                setUILoadingState(false);
            }
        };

        const loadChatHistory = async () => {
            addMessage('model', 'Connecting and loading your history...');
            try {
                const response = await fetch(`/history?userId=${userId}`);
                if (!response.ok) throw new Error('Failed to fetch history');
                const history = await response.json();
                chatWindow.innerHTML = ''; // Clear the loading message
                if (history.length === 0) {
                     addMessage('model', "Hello! I'm the Campus Helper chatbot. How can I assist you today?");
                } else {
                    history.forEach(item => addMessage(item.sender, item.message));
                }
            } catch (error) {
                console.error("Error loading chat history:", error);
                chatWindow.innerHTML = '';
                addMessage('model', "Could not load history. Starting a new session.");
            }
        };

        chatForm.addEventListener('submit', (e) => {
            e.preventDefault();
            const userMessage = chatInput.value.trim();
            if (userMessage && !isLoading) {
                addMessage('user', userMessage);
                chatInput.value = '';
                getBotResponse(userMessage);
            }
        });

        window.addEventListener('load', loadChatHistory);
    </script>
</body>
</html>
"""

# --- FLASK ROUTES ---

@app.route('/')
def index():
    """Serves the main HTML page."""
    return render_template_string(HTML_TEMPLATE)

@app.route('/history')
def get_history():
    """Fetches chat history from Firestore."""
    user_id = request.args.get('userId')
    if not user_id:
        return jsonify({"error": "userId is required"}), 400
    
    try:
        messages_ref = db.collection('artifacts', APP_ID, 'users', user_id, 'messages').order_by('timestamp', direction=firestore.Query.ASCENDING)
        docs = messages_ref.stream()
        history = [{"sender": doc.get("sender"), "message": doc.get("message")} for doc in docs]
        return jsonify(history)
    except Exception as e:
        print(f"Error fetching history for {user_id}: {e}")
        return jsonify({"error": "Could not fetch history"}), 500


@app.route('/chat', methods=['POST'])
def chat():
    """Handles chat messages, gets AI response, and saves to DB."""
    data = request.json
    user_id = data.get('userId')
    user_message = data.get('message')
    language = data.get('language', 'English')

    if not all([user_id, user_message]):
        return jsonify({"error": "userId and message are required"}), 400

    try:
        # 1. Save user message to Firestore
        messages_ref = db.collection('artifacts', APP_ID, 'users', user_id, 'messages')
        messages_ref.add({
            'sender': 'user',
            'message': user_message,
            'timestamp': firestore.SERVER_TIMESTAMP
        })

        # 2. Get AI response
        model = genai.GenerativeModel(
            model_name='gemini-1.5-flash',
            system_instruction=get_system_prompt(language)
        )
        response = model.generate_content(f"Query in {language}: {user_message}")
        bot_reply = response.text

        # 3. Save bot response to Firestore
        messages_ref.add({
            'sender': 'model',
            'message': bot_reply,
            'timestamp': firestore.SERVER_TIMESTAMP
        })

        return jsonify({"reply": bot_reply})

    except Exception as e:
        print(f"Error in /chat endpoint: {e}")
        return jsonify({"error": "An error occurred while processing your request."}), 500

# --- MAIN EXECUTION ---

if __name__ == '__main__':
    # Use debug=True for development, but turn it off for production
    app.run(debug=True)
