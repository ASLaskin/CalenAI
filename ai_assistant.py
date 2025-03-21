import requests
import json
import re
from typing import List, Dict, Any

def is_ollama_running() -> bool:
    try:
        response = requests.get("http://localhost:11434/api/version", timeout=2)
        if response.status_code == 200:
            return True
    except requests.exceptions.RequestException:
        pass
    return False

def extract_calendar_operations(response: str, calendar_manager) -> List[Dict[str, Any]]:
    operations = []
    
    json_pattern = r'```(?:json)?\s*(\{[\s\S]*?\})\s*```'
    json_blocks = re.findall(json_pattern, response, re.DOTALL)
    
    if not json_blocks:
        json_pattern = r'\{[\s\S]*?"calendar_operations"\s*:\s*\[[\s\S]*?\]\s*\}'
        json_blocks = re.findall(json_pattern, response, re.DOTALL)
    
    for i, json_block in enumerate(json_blocks):
        try:
            # print(f"DEBUG: Found JSON block {i+1}:\n{json_block}")
            data = json.loads(json_block)
            if "calendar_operations" in data:
                operations = data["calendar_operations"]
                break
        except json.JSONDecodeError as e:
            try:
                cleaned_json = json_block.replace("'", '"') 
                data = json.loads(cleaned_json)
                if "calendar_operations" in data:
                    operations = data["calendar_operations"]
                    # print(f"DEBUG: Successfully extracted {len(operations)} operations after cleaning")
                    break
            except json.JSONDecodeError:
                print(f"DEBUG: Failed to parse JSON block {i+1} even after cleaning")
                continue
    
    return operations

def process_calendar_operations(operations: List[Dict[str, Any]], calendar_manager) -> str:
    result = []
    
    for op in operations:
        op_type = op.get("operation")
        
        if op_type == "add_event":
            date_str = op.get("date")
            start_time = op.get("start_time")
            end_time = op.get("end_time")
            title = op.get("title")
            description = op.get("description", "")
            
            if all([date_str, start_time, end_time, title]):
                event_id = calendar_manager.add_event(date_str, start_time, end_time, title, description)
                result.append(f"Added event: {title} at {start_time}-{end_time} on {date_str}")
        
        elif op_type == "delete_event":
            date_str = op.get("date")
            event_id = op.get("event_id")
            
            if date_str and event_id:
                success = calendar_manager.delete_event(date_str, event_id)
                if success:
                    result.append(f"Deleted event with ID {event_id}")
        
        elif op_type == "delete_events_by_title":
            title = op.get("title")
            
            if title:
                deleted = calendar_manager.delete_events_by_title(title)
                if deleted:
                    result.append(f"Deleted {len(deleted)} events with title containing '{title}'")
        
        elif op_type == "update_event":
            date_str = op.get("date")
            event_id = op.get("event_id")
            updated_fields = op.get("fields", {})
            
            if date_str and event_id and updated_fields:
                success = calendar_manager.update_event(date_str, event_id, updated_fields)
                if success:
                    fields_str = ", ".join([f"{k}: {v}" for k, v in updated_fields.items()])
                    result.append(f"Updated event {event_id}: {fields_str}")
        
        elif op_type == "move_event":
            old_date = op.get("old_date")
            new_date = op.get("new_date")
            event_id = op.get("event_id")
            
            if old_date and new_date and event_id:
                success = calendar_manager.move_event(old_date, event_id, new_date)
                if success:
                    result.append(f"Moved event {event_id} from {old_date} to {new_date}")
        
        elif op_type == "clear_day":
            date_str = op.get("date")
            
            if date_str:
                removed = calendar_manager.clear_day(date_str)
                if removed:
                    result.append(f"Cleared {len(removed)} events from {date_str}")
        
        elif op_type == "reorganize_day":
            date_str = op.get("date")
            schedule = op.get("schedule", [])
            
            if date_str and schedule:
                success = calendar_manager.reorganize_day(date_str, schedule)
                if success:
                    result.append(f"Reorganized schedule for {date_str} with {len(schedule)} events")
    
    return "\n".join(result) if result else "No calendar operations performed."

def query_ollama(prompt: str, calendar_manager, model: str = "llama3.2", temperature: float = 0.7) -> str:
    api_url = "http://localhost:11434/api/generate"
    
    calendar_context = calendar_manager.get_calendar_context()

    system_instructions = """
You are a calendar assistant named Jared with direct control over the user's schedule. You add, delete, update, and reorganize events.

For any calendar action, always include a JSON block with calendar_operations in your response.

When adding events, include JSON in this format:
```json
{
  "calendar_operations": [
    {
      "operation": "add_event",
      "date": "YYYY-MM-DD",
      "start_time": "HH:MM(am/pm)",
      "end_time": "HH:MM(am/pm)",
      "title": "Event title",
      "description": "Optional description"
    },
    {
      "operation": "delete_event",
      "date": "YYYY-MM-DD",
      "event_id": "id_of_event_to_delete"
    },
    {
      "operation": "update_event",
      "date": "YYYY-MM-DD",
      "event_id": "id_of_event_to_update",
      "fields": {
        "title": "New title",
        "start_time": "New start time",
        "end_time": "New end time",
        "description": "New description"
    }
  ]
}
```

For simple requests like "add a meeting at 3pm" or "meeting at 5pm" you MUST include the JSON block with the complete operation details including the date (use current date if not specified).

Other operations follow similar formats. Always add a friendly message after the JSON block.

For example, when someone asks to add a meeting, respond like:
"I've added your meeting to the calendar! Here are the details:

```json
{
  "calendar_operations": [
    {
      "operation": "add_event",
      "date": "2025-03-14",
      "start_time": "3:00pm",
      "end_time": "4:00pm",
      "title": "Meeting",
      "description": ""
    }
  ]
}
```
When creating a schedule, organize events efficiently with appropriate breaks. Consider normal working hours (9am-5pm) unless specified otherwise.

If the user says:
- "Add meeting at 9pm for tomorrow" - Create a new event
- "Move my gym session to 5pm" - Update an existing event
- "Clear my schedule for Friday" - Remove all events for a day
- "Reorganize my day to fit in 1 hour of reading" - Adjust the schedule
- "I want to go to the gym for an hour and read for 2 hours" - Create a reasonable schedule

If an action was performed to the calender MAKE SURE TO add a confirmation message
- Example: Successfully added the dinner tomorrow, enjoy! "

RULES
-NEVER RESPOND WITH THE UPDATED CALENDER
-ALWAYS INCLUDE A JSON IF UPDATE/CHANGE NECESSARY
-INCLUDE A NICE MESSAGE AFTER JSON
"""
    
    full_prompt = f"{system_instructions}\n\n{calendar_context}\n\nHuman: {prompt}\nAssistant:"
    
    try:
        response = requests.post(api_url, json={
            "model": model,
            "prompt": full_prompt,
            "stream": False,
            "temperature": temperature
        })
        response.raise_for_status()
        
        ai_response = response.json().get("response", "No response received")

        # print("DEBUG: Raw AI response length:", len(ai_response))
        
        operations = extract_calendar_operations(ai_response, calendar_manager)
        process_result = ""
        
        if operations:
            # print("DEBUG: Operations extracted successfully:", operations)
            process_result = process_calendar_operations(operations, calendar_manager)
            
            json_pattern = r'```(?:json)?\s*(\{[\s\S]*?\})\s*```'
            ai_response = re.sub(json_pattern, '', ai_response, flags=re.DOTALL)
            ai_response = ai_response.strip()
            
            # if process_result and "No calendar operations performed" not in process_result:
            #     ai_response += f"\n\n[Calendar updated: {process_result}]"
        else:
            print("DEBUG: No operations extracted from response")
        
        return ai_response
    except requests.exceptions.RequestException as e:
        print(f"DEBUG: Request error: {str(e)}")
        return f"Error: {str(e)}"