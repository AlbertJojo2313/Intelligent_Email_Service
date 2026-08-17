from typing import Any


class FallbackGenerator:
    def __init__(self, templates: dict[str, list[str]]):
        self.templates = templates

    def generate(
        self, topic: str, advisor_name: str, client_name: str, thread_count: int
    ) -> list[dict[str, Any]]:
        """
        Generates thread messages using local predefined templates when LLM service is unavailable.
        """
        templates = self.templates.get(topic, self.templates.get("default", []))
        if not templates:
            raise ValueError(
                f"No fallback templates found for topic '{topic}' or 'default'."
            )

        bodies = []
        for i in range(thread_count):
            template = templates[i % len(templates)]
            body = template.format(advisor_name=advisor_name, client_name=client_name)

            sender = "client" if i % 2 == 0 else "advisor"
            subject = (
                f"Re: {topic.replace('_', ' ').title()}"
                if i > 0
                else topic.replace("_", " ").title()
            )

            if i > 0 and not subject.lower().startswith("re:"):
                subject = f"Re: {subject}"

            bodies.append({"sender": sender, "subject": subject, "body": body})

        return bodies
