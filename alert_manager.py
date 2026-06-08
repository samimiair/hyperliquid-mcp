"""Alert management for monitoring and notifications."""
from typing import Any, Dict, Optional


class AlertManager:
    """Alert management – logs and sends notifications."""

    def __init__(self):
        self.alerts: list[Dict[str, Any]] = []
        self.webhooks: list[str] = []

    async def send_alert(
        self,
        severity: str,
        title: str,
        message: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        alert = {
            "severity": severity,
            "title": title,
            "message": message,
            "data": data,
            "timestamp": __import__("datetime").datetime.now().isoformat(),
        }
        self.alerts.append(alert)

        emoji = {
            "CRITICAL": "🔴",
            "WARNING": "🟡",
            "ERROR": "❌",
        }.get(severity, "ℹ️")
        print(f"{emoji} [{severity}] {title}: {message}")

        for webhook in self.webhooks:
            try:
                pass  # would POST to webhook URL here
            except Exception:
                pass

        return alert

    def add_webhook(self, url: str):
        self.webhooks.append(url)

    def get_alerts(self, limit: int = 100) -> list:
        return self.alerts[-limit:]
