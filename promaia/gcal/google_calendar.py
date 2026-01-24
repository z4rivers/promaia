"""
Google Calendar integration for scheduling agents.

This allows agents to be managed like team members on your calendar:
- Create recurring calendar events for agents
- Agents run when their calendar event triggers
- Manage scheduling visually in Google Calendar
"""

import os
import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from pathlib import Path
import json

logger = logging.getLogger(__name__)


class GoogleCalendarManager:
    """Manage agents as Google Calendar events."""

    def __init__(self, credentials_path: Optional[str] = None):
        """
        Initialize Google Calendar manager.

        Args:
            credentials_path: Path to credentials.json file
        """
        self.credentials_path = credentials_path or self._get_default_credentials_path()
        self.service = None
        self.calendar_id = "primary"  # Use primary calendar by default

    def _get_default_credentials_path(self) -> str:
        """Get default path for Google Calendar credentials."""
        # Check common locations
        paths_to_check = [
            Path.home() / ".promaia" / "google_calendar_credentials.json",
            Path.cwd() / "google_calendar_credentials.json",
            Path.home() / ".config" / "promaia" / "google_calendar_credentials.json",
        ]

        for path in paths_to_check:
            if path.exists():
                return str(path)

        # Return default location even if it doesn't exist yet
        return str(Path.home() / ".promaia" / "google_calendar_credentials.json")

    def authenticate(self) -> bool:
        """
        Authenticate with Google Calendar API.

        Returns:
            True if authentication successful, False otherwise
        """
        try:
            from google.oauth2.credentials import Credentials
            from google_auth_oauthlib.flow import InstalledAppFlow
            from google.auth.transport.requests import Request
            from googleapiclient.discovery import build

            SCOPES = ['https://www.googleapis.com/auth/calendar']

            creds = None
            token_path = Path.home() / ".promaia" / "google_calendar_token.json"

            # Load existing token
            if token_path.exists():
                creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

            # If no valid credentials, authenticate
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                else:
                    if not Path(self.credentials_path).exists():
                        logger.error(f"Credentials file not found: {self.credentials_path}")
                        logger.error("Download credentials from Google Cloud Console and save to this path")
                        return False

                    flow = InstalledAppFlow.from_client_secrets_file(
                        self.credentials_path, SCOPES)
                    creds = flow.run_local_server(port=0)

                # Save the credentials for next time
                token_path.parent.mkdir(parents=True, exist_ok=True)
                with open(token_path, 'w') as token:
                    token.write(creds.to_json())

            # Build service
            self.service = build('calendar', 'v3', credentials=creds)
            logger.info("Successfully authenticated with Google Calendar")
            return True

        except ImportError:
            logger.error("Google Calendar API libraries not installed")
            logger.error("Install with: pip install google-auth-oauthlib google-auth-httplib2 google-api-python-client")
            return False
        except Exception as e:
            logger.error(f"Error authenticating with Google Calendar: {e}")
            return False

    def create_agent_event(
        self,
        agent_name: str,
        schedule: List[tuple],  # [(day, time), ...]
        agent_config: Dict[str, Any],
        calendar_id: Optional[str] = None
    ) -> Optional[str]:
        """
        Create recurring calendar events for an agent.

        Args:
            agent_name: Name of the agent
            schedule: List of (day, time) tuples like [("Mon", "09:00"), ...]
            agent_config: Full agent configuration
            calendar_id: Optional calendar ID (defaults to primary)

        Returns:
            Event ID if successful, None otherwise
        """
        if not self.service:
            if not self.authenticate():
                return None

        cal_id = calendar_id or self.calendar_id

        try:
            # Group schedule by unique times to create fewer events with multiple recurrences
            # For now, create one event per schedule entry
            # Future optimization: group by time and create RRULE with BYDAY

            event_ids = []

            for day, time in schedule:
                # Parse time
                hour, minute = map(int, time.split(':'))

                # Map day names to weekday numbers (MO, TU, WE, etc.)
                day_map = {
                    "Mon": "MO", "Tue": "TU", "Wed": "WE",
                    "Thu": "TH", "Fri": "FR", "Sat": "SA", "Sun": "SU"
                }
                weekday = day_map.get(day, "MO")

                # Create event
                # Start from next occurrence of this day
                today = datetime.now()
                days_ahead = (list(day_map.keys()).index(day) - today.weekday()) % 7
                if days_ahead == 0:
                    days_ahead = 7  # Start from next week

                next_occurrence = today + timedelta(days=days_ahead)
                start_datetime = next_occurrence.replace(
                    hour=hour,
                    minute=minute,
                    second=0,
                    microsecond=0
                )

                # Event lasts 5 minutes (just a placeholder)
                end_datetime = start_datetime + timedelta(minutes=5)

                event = {
                    'summary': f'🤖 {agent_name}',
                    'description': self._format_agent_description(agent_config),
                    'start': {
                        'dateTime': start_datetime.isoformat(),
                        'timeZone': 'UTC',
                    },
                    'end': {
                        'dateTime': end_datetime.isoformat(),
                        'timeZone': 'UTC',
                    },
                    'recurrence': [
                        f'RRULE:FREQ=WEEKLY;BYDAY={weekday}'
                    ],
                    'reminders': {
                        'useDefault': False,
                        'overrides': [],
                    },
                    # Store agent metadata in extended properties
                    'extendedProperties': {
                        'private': {
                            'promaia_agent': 'true',
                            'agent_name': agent_name,
                            'agent_schedule_entry': f'{day}_{time}'
                        }
                    },
                    # Use a specific color for agents
                    'colorId': '9'  # Blue color
                }

                result = self.service.events().insert(calendarId=cal_id, body=event).execute()
                event_ids.append(result.get('id'))
                logger.info(f"Created calendar event for {agent_name} on {day} at {time}")

            # Store all event IDs in agent metadata
            return ','.join(event_ids)

        except Exception as e:
            logger.error(f"Error creating calendar event: {e}")
            return None

    def _format_agent_description(self, agent_config: Dict[str, Any]) -> str:
        """Format agent config as calendar event description."""
        parts = [
            f"Promaia Agent: {agent_config.get('name')}",
            "",
            f"Workspace: {agent_config.get('workspace')}",
            f"Databases: {', '.join(agent_config.get('databases', []))}",
            f"Output: {agent_config.get('output_notion_page_id')}",
        ]

        if agent_config.get('description'):
            parts.extend(["", agent_config['description']])

        parts.extend([
            "",
            "---",
            "This event is managed by Promaia.",
            "The agent will run automatically when this event occurs."
        ])

        return "\n".join(parts)

    def delete_agent_events(
        self,
        agent_name: str,
        calendar_id: Optional[str] = None
    ) -> bool:
        """
        Delete all calendar events for an agent.

        Args:
            agent_name: Name of the agent
            calendar_id: Optional calendar ID

        Returns:
            True if successful
        """
        if not self.service:
            if not self.authenticate():
                return False

        cal_id = calendar_id or self.calendar_id

        try:
            # Search for events with this agent name
            events_result = self.service.events().list(
                calendarId=cal_id,
                privateExtendedProperty=f'agent_name={agent_name}',
                maxResults=100
            ).execute()

            events = events_result.get('items', [])

            for event in events:
                self.service.events().delete(
                    calendarId=cal_id,
                    eventId=event['id']
                ).execute()
                logger.info(f"Deleted calendar event {event['id']} for {agent_name}")

            return True

        except Exception as e:
            logger.error(f"Error deleting calendar events: {e}")
            return False

    def list_agent_events(
        self,
        agent_name: Optional[str] = None,
        calendar_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        List all agent events on the calendar.

        Args:
            agent_name: Optional filter by agent name
            calendar_id: Optional calendar ID

        Returns:
            List of event dictionaries
        """
        if not self.service:
            if not self.authenticate():
                return []

        cal_id = calendar_id or self.calendar_id

        try:
            # Search for agent events
            query = 'promaia_agent=true'
            if agent_name:
                query = f'agent_name={agent_name}'

            events_result = self.service.events().list(
                calendarId=cal_id,
                privateExtendedProperty=query,
                maxResults=100,
                singleEvents=False  # Include recurring events
            ).execute()

            return events_result.get('items', [])

        except Exception as e:
            logger.error(f"Error listing calendar events: {e}")
            return []

    def get_upcoming_agent_runs(
        self,
        hours_ahead: int = 24,
        calendar_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get upcoming agent runs in the next N hours.

        Args:
            hours_ahead: How many hours to look ahead
            calendar_id: Optional calendar ID

        Returns:
            List of upcoming events with agent metadata
        """
        if not self.service:
            if not self.authenticate():
                return []

        cal_id = calendar_id or self.calendar_id

        try:
            # Get upcoming events
            now = datetime.utcnow()
            time_max = now + timedelta(hours=hours_ahead)

            events_result = self.service.events().list(
                calendarId=cal_id,
                timeMin=now.isoformat() + 'Z',
                timeMax=time_max.isoformat() + 'Z',
                privateExtendedProperty='promaia_agent=true',
                singleEvents=True,  # Expand recurring events
                orderBy='startTime'
            ).execute()

            events = events_result.get('items', [])

            # Extract agent info
            upcoming = []
            for event in events:
                props = event.get('extendedProperties', {}).get('private', {})
                if props.get('promaia_agent') == 'true':
                    upcoming.append({
                        'event_id': event['id'],
                        'agent_name': props.get('agent_name'),
                        'start': event['start'].get('dateTime'),
                        'summary': event.get('summary'),
                    })

            return upcoming

        except Exception as e:
            logger.error(f"Error getting upcoming runs: {e}")
            return []


def get_calendar_manager() -> GoogleCalendarManager:
    """Get singleton calendar manager instance."""
    global _calendar_manager
    if '_calendar_manager' not in globals():
        _calendar_manager = GoogleCalendarManager()
    return _calendar_manager
