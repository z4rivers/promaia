import logging
from datetime import datetime, timedelta, timezone
from google.genai import types

logger = logging.getLogger(__name__)

async def handle(ft) -> types.FunctionResponse:
    if ft.name == "create_calendar_event":
        args = ft.args
        try:
            from promaia.gcal.google_calendar import get_calendar_manager
            mgr = get_calendar_manager()
            if mgr.authenticate():
                event_body = {
                    'summary': args.get('summary'),
                    'start': {'dateTime': args.get('start_time'), 'timeZone': 'America/Los_Angeles'},
                    'end': {'dateTime': args.get('end_time'), 'timeZone': 'America/Los_Angeles'}
                }
                if args.get('description'):
                    event_body['description'] = args.get('description')
                
                if 'Z' in str(args.get('start_time')):
                    event_body['start']['timeZone'] = 'UTC'
                    event_body['end']['timeZone'] = 'UTC'

                event = mgr.service.events().insert(
                    calendarId='primary',
                    body=event_body
                ).execute()
                
                return types.FunctionResponse(
                    name=ft.name,
                    id=ft.id,
                    response={"result": "event_created", "event_id": event.get('id'), "link": event.get('htmlLink')}
                )
            else:
                return types.FunctionResponse(
                    name=ft.name,
                    id=ft.id,
                    response={"result": "authentication_failed", "error": "Google Calendar authentication failed"}
                )
        except Exception as e:
            logger.error(f"Failed to create calendar event: {e}", exc_info=True)
            return types.FunctionResponse(
                name=ft.name,
                id=ft.id,
                response={"result": "error_creating_event", "error": str(e)}
            )

    elif ft.name == "delete_calendar_event":
        args = ft.args
        try:
            from promaia.gcal.google_calendar import get_calendar_manager
            mgr = get_calendar_manager()
            if mgr.authenticate():
                search_summary = args.get('summary', '').lower()
                search_date = args.get('date')
                
                now_dt = datetime.now(timezone.utc)
                time_max = now_dt + timedelta(days=90)
                if search_date:
                    from datetime import date as date_type
                    try:
                        d = datetime.strptime(search_date, '%Y-%m-%d')
                        search_start = d.replace(hour=0, minute=0, second=0, tzinfo=timezone.utc)
                        time_max = d.replace(hour=23, minute=59, second=59, tzinfo=timezone.utc)
                        now_dt = search_start
                    except ValueError:
                        pass
                
                events_result = mgr.service.events().list(
                    calendarId='primary',
                    timeMin=now_dt.isoformat().replace('+00:00', 'Z'),
                    timeMax=time_max.isoformat().replace('+00:00', 'Z'),
                    singleEvents=True,
                    orderBy='startTime',
                    q=args.get('summary', '')
                ).execute()
                
                events = events_result.get('items', [])
                if events:
                    deleted = []
                    for ev in events:
                        if search_summary in ev.get('summary', '').lower():
                            mgr.service.events().delete(
                                calendarId='primary',
                                eventId=ev['id']
                            ).execute()
                            deleted.append(ev.get('summary'))
                    
                    if deleted:
                        return types.FunctionResponse(
                            name=ft.name,
                            id=ft.id,
                            response={"result": "events_deleted", "deleted": deleted}
                        )
                    else:
                        return types.FunctionResponse(
                            name=ft.name,
                            id=ft.id,
                            response={"result": "no_matching_events", "searched_for": args.get('summary')}
                        )
                else:
                    return types.FunctionResponse(
                        name=ft.name,
                        id=ft.id,
                        response={"result": "no_events_found", "searched_for": args.get('summary')}
                    )
            else:
                return types.FunctionResponse(
                    name=ft.name,
                    id=ft.id,
                    response={"result": "authentication_failed"}
                )
        except Exception as e:
            logger.error(f"Failed to delete calendar event: {e}", exc_info=True)
            return types.FunctionResponse(
                name=ft.name,
                id=ft.id,
                response={"result": "error_deleting_event", "error": str(e)}
            )
