import google.generativeai as genai
import os
from dotenv import load_dotenv

load_dotenv()

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

model = genai.GenerativeModel("gemini-2.5-flash")

chat_history = []   

def chat_with_gemini(prompt):
    try:
        response = model.generate_content(prompt)
        return response.text

    except Exception as e:
        return f"An error occurred: {str(e)}"

def get_oasis_response(user_input, emotion, persona="friend", user_preferences=None):
    chat_history.append(f"User: {user_input}")

    prompt = "\n".join(chat_history[-5:])

    prefs_context = ""
    if user_preferences:
        prefs_context = "\nUser Background & Preferences:\n"
        for key, val in user_preferences.items():
            prefs_context += f"- {key.replace('_', ' ').capitalize()}: {val}\n"

    userprompt = f"System: You are Oasis, a supportive mental wellness assistant. The user is currently feeling {emotion}. Your persona is {persona}. {prefs_context}\n\nChat History:\n{prompt}\n\nOasis:"

    gemini_response = chat_with_gemini(userprompt)
    chat_history.append(f"Bot: {gemini_response}")
    return gemini_response

if __name__ == "__main__":
    while True:
        user_input = input("You: ")
        if user_input.lower() in ["exit", "quit", "bye"]:
            print("Exiting the chat. Goodbye!")
            break

        response = get_oasis_response(user_input, 'neutral', 'friend')
        print(f"Oasis: {response}")
