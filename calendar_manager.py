import json
import os
import re
import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Any

class CalendarManager:
    def __init__(self, calendar_file="calendar_data.json"):
        self.calendar_file = calendar_file
        self.ensure_calendar_file()
        self.events = self.load_calendar()
    
    def ensure_calendar_file(self) -> None:
        if not os.path.exists(self.calendar_file):
            with open(self.calendar_file, 'w') as f:
                json.dump({}, f, indent=2)
    
    def load_calendar(self) -> Dict[str, List[Dict[str, Any]]]:
        try:
            with open(self.calendar_file, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            print(f"Warning: Could not parse calendar file. Starting with empty calendar.")
            return {}
    
    def save_calendar(self) -> None:
        with open(self.calendar_file, 'w') as f:
            json.dump(self.events, f, indent=2)

    
    def get_events_for_day(self, date_str: str) -> List[Dict[str, Any]]:
        return self.events.get(date_str, [])
    
    def add_event(self, date_str: str, start_time: str, end_time: str, title: str, description: str = "") -> str:
        if date_str not in self.events:
            self.events[date_str] = []
        
        event_id = str(uuid.uuid4())
        event = {
            "id": event_id,
            "title": title,
            "start_time": start_time,
            "end_time": end_time,
            "description": description
        }
        
        self.events[date_str].append(event)
        self.save_calendar()
        return event_id
    
    def delete_event(self, date_str: str, event_id: str) -> bool:
        if date_str in self.events:
            initial_length = len(self.events[date_str])
            self.events[date_str] = [e for e in self.events[date_str] if e["id"] != event_id]
            
            if len(self.events[date_str]) < initial_length:
                self.save_calendar()
                return True
        return False
    
    def delete_events_by_title(self, title: str) -> List[Dict[str, Any]]:
        deleted_events = []
        
        for date_str in self.events:
            before_count = len(self.events[date_str])
            matching_events = [e for e in self.events[date_str] if title.lower() in e["title"].lower()]
            self.events[date_str] = [e for e in self.events[date_str] if title.lower() not in e["title"].lower()]
            
            if before_count != len(self.events[date_str]):
                deleted_events.extend(matching_events)
        
        if deleted_events:
            self.save_calendar()
            
        return deleted_events
    
    def update_event(self, date_str: str, event_id: str, updated_fields: Dict[str, Any]) -> bool:
        if date_str in self.events:
            for event in self.events[date_str]:
                if event["id"] == event_id:
                    for key, value in updated_fields.items():
                        if key in event:
                            event[key] = value
                    self.save_calendar()
                    return True
        return False
    
    def move_event(self, old_date_str: str, event_id: str, new_date_str: str) -> bool:
        if old_date_str in self.events:
            event_to_move = None
            for i, event in enumerate(self.events[old_date_str]):
                if event["id"] == event_id:
                    event_to_move = event
                    self.events[old_date_str].pop(i)
                    break
            
            if event_to_move:
                if new_date_str not in self.events:
                    self.events[new_date_str] = []
                
                self.events[new_date_str].append(event_to_move)
                self.save_calendar()
                return True
        
        return False
    
    def clear_day(self, date_str: str) -> List[Dict[str, Any]]:
        removed_events = []
        if date_str in self.events:
            removed_events = self.events[date_str]
            self.events[date_str] = []
            self.save_calendar()
        
        return removed_events
    
    def reorganize_day(self, date_str: str, new_schedule: List[Dict[str, Any]]) -> bool:
        if date_str not in self.events:
            self.events[date_str] = []
        
        existing_events = {event["title"].lower(): event["id"] for event in self.events[date_str]}
        
        for event in new_schedule:
            if "id" not in event:
                if event["title"].lower() in existing_events:
                    event["id"] = existing_events[event["title"].lower()]
                else:
                    event["id"] = str(uuid.uuid4())
        
        self.events[date_str] = new_schedule
        self.save_calendar()
        return True
    
    def get_calendar_context(self, days_ahead: int = 7) -> str:
        context = "Current Calendar:\n"
        today = datetime.now().date()
        
        for i in range(days_ahead):
            date = today + timedelta(days=i)
            date_str = date.strftime("%Y-%m-%d")
            if i == 0:
                day_name = "Today"
            elif i == 1:
                day_name = "Tomorrow"
            else:
                day_name = date.strftime("%A, %b %d")
            
            context += f"\n{day_name} ({date_str}):\n"
            
            day_events = self.get_events_for_day(date_str)
            if day_events:
                sorted_events = sorted(day_events, key=lambda x: convert_to_24h(x["start_time"]))
                for event in sorted_events:
                    context += f"- {event['start_time']}-{event['end_time']}: {event['title']}"
                    if event['description']:
                        context += f" ({event['description']})"
                    context += f" [ID: {event['id']}]\n"
            else:
                context += "- No events scheduled\n"
        
        return context
    

def convert_to_24h(time_str: str) -> int:
    time_str = time_str.lower().strip()
    
    match = re.match(r'(\d+)(?::(\d+))?\s*(am|pm)', time_str)
    if match:
        hour = int(match.group(1))
        minute = int(match.group(2)) if match.group(2) else 0
        ampm = match.group(3)
        
        if ampm == 'pm' and hour < 12:
            hour += 12
        elif ampm == 'am' and hour == 12:
            hour = 0
            
        return hour * 60 + minute
    
    match = re.match(r'(\d+)(?::(\d+))?', time_str)
    if match:
        hour = int(match.group(1))
        minute = int(match.group(2)) if match.group(2) else 0
        return hour * 60 + minute
    
    return 0