import json
import time
import uuid

class WideLogger:
    def __init__(self, service_name, correlation_id=None):
        self.start_time = time.time()
        self.event = {
            "event_id": str(uuid.uuid4()),
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "service": service_name,
            "correlation_id": correlation_id,
            "steps": [],
            "context": {},
            "outcome": "unknown"
        }

    def log(self, level, message, **kwargs):
        """
        Logs a step in the process. 
        Also prints to stdout for immediate feedback (optional but useful for dev).
        """
        # Print for human-readable feedback during dev
        print(f"[{level}] {message}")
        
        step = {
            "t_ms": round((time.time() - self.start_time) * 1000, 2),
            "level": level,
            "message": message
        }
        step.update(kwargs)
        self.event["steps"].append(step)

    def info(self, message, **kwargs):
        self.log("INFO", message, **kwargs)

    def warning(self, message, **kwargs):
        self.log("WARNING", message, **kwargs)

    def error(self, message, error=None, **kwargs):
        self.log("ERROR", message, **kwargs)
        if error:
            self.event["error"] = {
                "type": type(error).__name__,
                "message": str(error)
            }

    def add_context(self, key, value):
        """Adds business context to the wide event."""
        self.event["context"][key] = value

    def finish(self, success=True):
        """Finalizes the event and emits the JSON."""
        self.event["duration_ms"] = round((time.time() - self.start_time) * 1000, 2)
        self.event["outcome"] = "success" if success else "failure"
        
        # This is the "Wide Event" emission
        print("WIDE_EVENT_JSON:" + json.dumps(self.event, default=str)) 
