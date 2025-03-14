import argparse
import json
import os
from datetime import datetime
from typing import List, Dict, Any
import speech_recognition as sr

from calendar_manager import CalendarManager
from ai_assistant import query_ollama, is_ollama_running

def load_history(file_path: str) -> List[Dict[str, Any]]:
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            print(f"Warning: Could not parse history file {file_path}. Starting with empty history.")
            return []
    return []

def save_history(history: List[Dict[str, Any]], file_path: str) -> None:
    with open(file_path, 'w') as f:
        json.dump(history, f, indent=2)

def transcribe_audio(recognizer, microphone):
    with microphone as source:
        print("Listening... (speak now)")
        recognizer.adjust_for_ambient_noise(source, duration=1)
        try:
            audio = recognizer.listen(source, timeout=5, phrase_time_limit=15)
            print("Processing your speech...")
            text = recognizer.recognize_google(audio)
            print(f"You said: {text}")
            return text
        except sr.WaitTimeoutError:
            print("No speech detected. Try again.")
            return None
        except sr.UnknownValueError:
            print("Could not understand the audio. Try again.")
            return None
        except sr.RequestError as e:
            print(f"Error with speech recognition service: {e}")
            return None

def main():
    parser = argparse.ArgumentParser(description="Voice Calendar Assistant using Ollama")
    parser.add_argument("--model", type=str, default="llama3.2",
                        help="Model to use (default: llama3.2)")
    parser.add_argument("--temperature", type=float, default=0.7,
                        help="Temperature for generation (default: 0.7)")
    parser.add_argument("--history-file", type=str, default="calendar_history.json",
                        help="File to store conversation history (default: calendar_history.json)")
    parser.add_argument("--calendar-file", type=str, default="calendar_data.json",
                        help="File to store calendar data (default: calendar_data.json)")
    parser.add_argument("--text-input", action="store_true",
                        help="Use text input instead of voice")
    
    args = parser.parse_args()
    
    if not is_ollama_running():
        print("Ollama server is not running.")
        print("Please start Ollama server manually by running 'ollama serve' in a separate terminal.")
        return
    
    calendar_manager = CalendarManager(args.calendar_file)
    
    history_file = args.history_file
    history = load_history(history_file)
    
    print("Calendar Assistant Jared - Ready to help organize your schedule")
    print(f"Using model: {args.model}")
    
    recognizer = sr.Recognizer()
    microphone = sr.Microphone()
    
    if not args.text_input:
        print("Adjusting for ambient noise... Please wait.")
        with microphone as source:
            recognizer.adjust_for_ambient_noise(source, duration=2)
    
    try:
        while True:
            prompt = None
            
            if args.text_input:
                lines = []
                while True:
                    line = input("> " if not lines else "  ")
                    if not line and lines:
                        break
                    if line.lower() in ["exit", "quit"]:
                        save_history(history, history_file)
                        print(f"Conversation history saved to {history_file}")
                        return
                    lines.append(line)
                
                if lines:
                    prompt = "\n".join(lines)
            else:
                print("\nPress Enter to start speaking, or type 'exit' to quit:")
                user_input = input()
                
                if user_input.lower() in ["exit", "quit"]:
                    save_history(history, history_file)
                    print(f"Conversation history saved to {history_file}")
                    return
                
                prompt = transcribe_audio(recognizer, microphone)
            
            if not prompt:
                continue
            
            print("\nThinking...")
            
            response = query_ollama(prompt, calendar_manager, history, args.model, args.temperature)
            # print("\n" + response + "\n")
            
            history.append({
                "timestamp": datetime.now().isoformat(),
                "prompt": prompt,
                "response": response
            })
            
            save_history(history, history_file)
            
    except KeyboardInterrupt:
        print("\nExiting...")
        save_history(history, history_file)
        print(f"Conversation history saved")

if __name__ == "__main__":
    main()