from pathlib import Path
from typing import Any, Dict

from jinja2 import Template


def render_template(name: str, variables: Dict[str, Any] = {}) -> str:
    """Render a Jinja2 template with provided variables.

    Loads a template file from the templates/ directory and renders it
    with the given variables.

    Args:
        name: Template name without extension (e.g., 'market' for 'market.jinja').
        variables: Dictionary of variables to pass to the template.

    Returns:
        Rendered template as a string.
    """
    template_path = Path('templates') / f'{name}.jinja'
    with open(template_path, 'r', encoding='utf-8') as t:
        template = Template(t.read())

    renderized_template = template.render(**variables)

    return renderized_template
